"""Tests for the DeviceToken registration / list / deactivation endpoint."""
import pytest
from rest_framework.test import APIClient

from notifications.models import DeviceToken

DEVICES = "/api/v1/notifications/devices/"


@pytest.mark.django_db
def test_register_device_token_creates_row(admin_user):
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.post(
        DEVICES,
        {"platform": "ios", "token": "tok-1", "app_version": "0.1.0"},
        format="json",
    )
    assert resp.status_code == 201
    obj = DeviceToken.objects.get(token="tok-1")
    assert obj.user == admin_user
    assert obj.platform == "ios"
    assert obj.is_active is True


@pytest.mark.django_db
def test_repeat_registration_is_upsert_not_duplicate(admin_user):
    api = APIClient()
    api.force_authenticate(admin_user)
    api.post(DEVICES, {"platform": "ios", "token": "tok-1"}, format="json")
    resp = api.post(
        DEVICES,
        {"platform": "ios", "token": "tok-1", "app_version": "0.2.0"},
        format="json",
    )
    # Second POST is an update, not a new row.
    assert resp.status_code == 200
    assert DeviceToken.objects.filter(token="tok-1").count() == 1
    assert DeviceToken.objects.get(token="tok-1").app_version == "0.2.0"


@pytest.mark.django_db
def test_token_rebinds_when_a_new_user_registers_it(admin_user, engineer_user):
    api = APIClient()
    api.force_authenticate(admin_user)
    api.post(DEVICES, {"platform": "android", "token": "shared"}, format="json")
    # The engineer logs in on the same phone -> same FCM token.
    api.force_authenticate(engineer_user)
    resp = api.post(
        DEVICES, {"platform": "android", "token": "shared"}, format="json"
    )
    assert resp.status_code == 200
    assert DeviceToken.objects.filter(token="shared").count() == 1
    assert DeviceToken.objects.get(token="shared").user == engineer_user


@pytest.mark.django_db
def test_list_only_returns_my_devices(admin_user, engineer_user):
    DeviceToken.objects.create(user=admin_user, platform="ios", token="mine")
    DeviceToken.objects.create(user=engineer_user, platform="ios", token="theirs")
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.get(DEVICES)
    assert resp.status_code == 200
    tokens = {row["token"] for row in resp.data["results"]}
    assert tokens == {"mine"}


@pytest.mark.django_db
def test_delete_deactivates_rather_than_removes(admin_user):
    obj = DeviceToken.objects.create(user=admin_user, platform="ios", token="tok-d")
    api = APIClient()
    api.force_authenticate(admin_user)
    resp = api.delete(f"{DEVICES}{obj.pk}/")
    assert resp.status_code == 204
    obj.refresh_from_db()
    assert obj.is_active is False


@pytest.mark.django_db
def test_anonymous_cannot_register(db):
    api = APIClient()
    resp = api.post(DEVICES, {"platform": "ios", "token": "x"}, format="json")
    assert resp.status_code in (401, 403)
