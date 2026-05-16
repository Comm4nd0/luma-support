"""UniFi integration + refresh_unifi_devices task."""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
import respx

from clients.models import System, SystemType
from notifications.models import Notification
from system.integrations.unifi import (
    UnifiDevice,
    UnifiResult,
    fetch_devices,
    health_from,
    serialise,
)
from system.tasks import refresh_unifi_devices

pytestmark = pytest.mark.django_db


# ----- health classification (pure) ------------------------------------


def test_health_from_empty_inventory_is_down():
    assert health_from(UnifiResult(devices=[])) == "down"


def test_health_from_all_online_is_ok():
    r = UnifiResult(devices=[UnifiDevice("a", "n", "m", 1, "1.2.3.4", 0)])
    assert health_from(r) == "ok"


def test_health_from_mixed_is_degraded():
    r = UnifiResult(
        devices=[
            UnifiDevice("a", "n1", "m", 1, "1.2.3.4", 0),
            UnifiDevice("b", "n2", "m", 0, "1.2.3.5", 0),
        ]
    )
    assert health_from(r) == "degraded"


def test_health_from_all_offline_is_down():
    r = UnifiResult(
        devices=[UnifiDevice("a", "n", "m", 0, "1.2.3.4", 0)]
    )
    assert health_from(r) == "down"


def test_serialise_shape():
    r = UnifiResult(
        devices=[
            UnifiDevice("aa:bb", "UAP", "U7PRO", 1, "10.0.0.5", 1700000000)
        ]
    )
    s = serialise(r)
    assert s["online"] == 1
    assert s["offline"] == 0
    assert s["total"] == 1
    assert s["devices"][0]["mac"] == "aa:bb"


# ----- HTTP client (with respx) ----------------------------------------


@respx.mock
def test_fetch_devices_happy_path():
    respx.post("https://unifi.example.com/api/auth/login").mock(
        return_value=httpx.Response(200, headers={"x-csrf-token": "tok"})
    )
    respx.get(
        "https://unifi.example.com/proxy/network/api/s/default/stat/device"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"mac": "aa", "name": "UAP-1", "state": 1, "ip": "10.0.0.5",
                     "last_seen": 1700, "model": "U7PRO"},
                    {"mac": "bb", "name": "Switch-1", "state": 0, "ip": "",
                     "last_seen": 0, "model": "USW8"},
                ]
            },
        )
    )

    result = fetch_devices("https://unifi.example.com", "admin", "hunter2")
    assert result.total == 2
    assert result.online == 1
    assert result.offline == 1


@respx.mock
def test_fetch_devices_raises_on_auth_failure():
    respx.post("https://unifi.example.com/api/auth/login").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(httpx.HTTPStatusError):
        fetch_devices("https://unifi.example.com", "admin", "wrong")


# ----- Celery task -----------------------------------------------------


def _make_network_system(client, *, monitoring_url="https://unifi", creds=None):
    s = System.objects.create(
        client=client,
        type=SystemType.NETWORK,
        name="Acme network",
        monitoring_url=monitoring_url,
    )
    if creds is None:
        creds = {"username": "admin", "password": "hunter2", "site": "default"}
    s.set_credentials(json.dumps(creds))
    s.save(update_fields=["credentials_encrypted"])
    return s


def test_refresh_skips_systems_without_url_or_creds(client_record):
    System.objects.create(
        client=client_record, type=SystemType.NETWORK, name="No URL"
    )
    System.objects.create(
        client=client_record,
        type=SystemType.NETWORK,
        name="No creds",
        monitoring_url="https://unifi",
    )

    with patch(
        "system.tasks.fetch_devices",
        side_effect=AssertionError("should not be called"),
    ):
        result = refresh_unifi_devices()
    assert "0 updated" in result


def test_refresh_persists_devices_and_marks_health(client_record):
    sys_ = _make_network_system(client_record)
    fake_result = UnifiResult(
        devices=[
            UnifiDevice("aa", "UAP", "U7", 1, "10.0.0.5", 1700),
            UnifiDevice("bb", "USW", "USW", 1, "10.0.0.6", 1700),
        ]
    )
    with patch("system.tasks.fetch_devices", return_value=fake_result):
        refresh_unifi_devices()

    sys_.refresh_from_db()
    assert sys_.health_status == "ok"
    assert sys_.last_checked_at is not None
    assert sys_.devices_json["online"] == 2
    assert sys_.devices_json["total"] == 2


def test_refresh_transition_to_down_fires_alert(client_record, admin_user, engineer_user):
    sys_ = _make_network_system(client_record)
    sys_.health_status = "ok"
    sys_.save(update_fields=["health_status"])

    # Simulate the controller being unreachable.
    with patch(
        "system.tasks.fetch_devices",
        side_effect=httpx.HTTPError("controller offline"),
    ):
        refresh_unifi_devices()

    sys_.refresh_from_db()
    assert sys_.health_status == "down"
    alerts = Notification.objects.filter(type=Notification.Type.SYSTEM_ALERT)
    assert alerts.count() == 2  # admin + engineer
    assert "Down" in alerts.first().title


def test_refresh_no_alert_when_status_unchanged(client_record, admin_user):
    sys_ = _make_network_system(client_record)
    sys_.health_status = "down"
    sys_.save(update_fields=["health_status"])

    with patch(
        "system.tasks.fetch_devices",
        side_effect=httpx.HTTPError("still down"),
    ):
        refresh_unifi_devices()

    assert Notification.objects.filter(
        type=Notification.Type.SYSTEM_ALERT
    ).count() == 0


def test_refresh_handles_bad_json_credentials(client_record):
    s = System.objects.create(
        client=client_record,
        type=SystemType.NETWORK,
        name="bad",
        monitoring_url="https://unifi",
    )
    s.set_credentials("not json")
    s.save(update_fields=["credentials_encrypted"])

    with patch(
        "system.tasks.fetch_devices",
        side_effect=AssertionError("should not be called"),
    ):
        result = refresh_unifi_devices()
    assert "0 updated" in result
