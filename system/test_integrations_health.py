"""Tests for /system/integrations/ and its underlying snapshot helper."""
import pytest
from django.test import Client as DjangoClient

from system.integrations_health import snapshot

pytestmark = pytest.mark.django_db


def test_snapshot_returns_one_row_per_check():
    rows = snapshot()
    names = {r["name"] for r in rows}
    assert {"anthropic", "stripe", "fcm", "imap_inbound", "xero", "unifi"} <= names
    for row in rows:
        assert {"name", "configured", "ok", "detail"} <= set(row.keys())


def test_anthropic_check_reflects_settings(settings):
    settings.ANTHROPIC_API_KEY = ""
    rows = {r["name"]: r for r in snapshot()}
    assert rows["anthropic"]["ok"] is False
    settings.ANTHROPIC_API_KEY = "sk-ant-test"
    rows = {r["name"]: r for r in snapshot()}
    assert rows["anthropic"]["ok"] is True


def test_integrations_endpoint_returns_json():
    web = DjangoClient()
    resp = web.get("/system/integrations/")
    assert resp.status_code == 200
    body = resp.json()
    assert "integrations" in body
    assert isinstance(body["integrations"], list)
    # all_ok summarises the configured-but-failing rows; it's bool either way.
    assert isinstance(body["all_ok"], bool)


def test_endpoint_does_not_require_auth():
    """Probe is intended to be consumable by external uptime monitors."""
    web = DjangoClient()
    resp = web.get("/system/integrations/")
    assert resp.status_code == 200
