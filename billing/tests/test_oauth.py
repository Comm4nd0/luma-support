from datetime import timedelta

import httpx
import pytest
import respx
from django.urls import reverse
from django.utils import timezone

from billing.models import XeroConnection
from billing.xero.client import XeroClient


@pytest.mark.django_db
def test_callback_rejects_bad_state(client, admin_user):
    client.force_login(admin_user)
    session = client.session
    session["xero_oauth_state"] = "good-state"
    session.save()
    resp = client.get(
        reverse("portal:xero_oauth_callback"),
        {"state": "bad-state", "code": "anything"},
    )
    assert resp.status_code == 400


@pytest.mark.django_db
@respx.mock
def test_callback_happy_path_creates_connection(client, admin_user, settings):
    settings.XERO_CLIENT_ID = "id"
    settings.XERO_CLIENT_SECRET = "secret"

    respx.post("https://identity.xero.com/connect/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "AT",
                "refresh_token": "RT",
                "expires_in": 1800,
                "token_type": "Bearer",
            },
        )
    )
    respx.get("https://api.xero.com/connections").mock(
        return_value=httpx.Response(
            200, json=[{"tenantId": "tenant-X", "tenantName": "Luma"}]
        )
    )

    client.force_login(admin_user)
    session = client.session
    session["xero_oauth_state"] = "s"
    session.save()
    resp = client.get(
        reverse("portal:xero_oauth_callback"), {"state": "s", "code": "C"}
    )
    assert resp.status_code == 302

    conn = XeroConnection.objects.get(pk=1)
    assert conn.tenant_id == "tenant-X"
    assert conn.access_token == "AT"
    assert conn.get_refresh_token() == "RT"
    # The encrypted column must not be the plaintext.
    assert conn.refresh_token_encrypted != "RT"


@pytest.mark.django_db
@respx.mock
def test_token_refresh_persists_rotated_refresh_token(xero_connection):
    # Force the connection to look expired so _ensure_fresh_token refreshes.
    XeroConnection.objects.filter(pk=1).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    xero_connection.refresh_from_db()

    respx.post("https://identity.xero.com/connect/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "AT-new",
                "refresh_token": "RT-rotated",
                "expires_in": 1800,
                "token_type": "Bearer",
            },
        )
    )

    api = XeroClient(xero_connection)
    api._ensure_fresh_token()

    fresh = XeroConnection.objects.get(pk=1)
    assert fresh.access_token == "AT-new"
    assert fresh.get_refresh_token() == "RT-rotated"
    assert fresh.expires_at > timezone.now()
