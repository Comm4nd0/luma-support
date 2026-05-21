"""Tests for the optional /admin/ IP allowlist middleware."""
import pytest
from django.test import Client as DjangoClient

pytestmark = pytest.mark.django_db


def test_no_allowlist_means_no_enforcement(admin_user, settings):
    settings.ADMIN_IP_ALLOWLIST = ""
    c = DjangoClient()
    c.force_login(admin_user)
    resp = c.get("/admin/")
    # 200 (admin index) or 302 (redirect to admin/login if not staff).
    assert resp.status_code in (200, 302)
    assert resp.status_code != 403


def test_allowlist_blocks_wrong_ip(admin_user, settings):
    settings.ADMIN_IP_ALLOWLIST = "10.0.0.1"
    c = DjangoClient()
    c.force_login(admin_user)
    resp = c.get("/admin/", REMOTE_ADDR="203.0.113.5")
    assert resp.status_code == 403


def test_allowlist_passes_matching_ip(admin_user, settings):
    settings.ADMIN_IP_ALLOWLIST = "10.0.0.1, 192.168.1.5"
    c = DjangoClient()
    c.force_login(admin_user)
    resp = c.get("/admin/", REMOTE_ADDR="192.168.1.5")
    assert resp.status_code != 403


def test_allowlist_honours_x_forwarded_for(admin_user, settings):
    settings.ADMIN_IP_ALLOWLIST = "1.2.3.4"
    c = DjangoClient()
    c.force_login(admin_user)
    resp = c.get(
        "/admin/",
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
    )
    assert resp.status_code != 403


def test_allowlist_only_applies_to_admin_paths(admin_user, settings):
    settings.ADMIN_IP_ALLOWLIST = "10.0.0.1"
    c = DjangoClient()
    c.force_login(admin_user)
    # Some non-admin URL — should not get a 403 from the middleware.
    resp = c.get("/dashboard/", REMOTE_ADDR="203.0.113.5")
    assert resp.status_code != 403
