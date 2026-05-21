"""TOTP enrolment + verification flow for the portal login."""
from __future__ import annotations

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def engineer():
    User = get_user_model()
    return User.objects.create_user(
        email="eng@luma.test", password="goodpass", role=User.Role.ENGINEER
    )


@pytest.fixture
def client_user_with_password(client_record):
    User = get_user_model()
    return User.objects.create_user(
        email="alice@acme.test",
        password="goodpass",
        role=User.Role.CLIENT,
        client=client_record,
    )


# ----- login routing ---------------------------------------------------


def test_engineer_password_login_is_redirected_to_setup(engineer):
    c = DjangoClient()
    resp = c.post(
        reverse("portal:login"),
        {"email": "eng@luma.test", "password": "goodpass"},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("portal:totp_setup")
    # Not yet authenticated — session is gated.
    assert "_auth_user_id" not in c.session
    assert c.session["pending_totp_user_id"] == engineer.pk


def test_engineer_with_enabled_totp_is_redirected_to_verify(engineer):
    secret = pyotp.random_base32()
    engineer.set_totp_secret(secret)
    engineer.totp_enabled = True
    engineer.save()
    c = DjangoClient()
    resp = c.post(
        reverse("portal:login"),
        {"email": "eng@luma.test", "password": "goodpass"},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("portal:totp_verify")
    assert "_auth_user_id" not in c.session


def test_client_user_skips_totp(client_user_with_password):
    c = DjangoClient()
    resp = c.post(
        reverse("portal:login"),
        {"email": "alice@acme.test", "password": "goodpass"},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("portal:dashboard")
    assert "_auth_user_id" in c.session


# ----- enrolment -------------------------------------------------------


def test_setup_get_renders_secret_and_qr_url(engineer):
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    resp = c.get(reverse("portal:totp_setup"))
    assert resp.status_code == 200
    assert b"2fa/qr.svg" in resp.content


def test_setup_post_with_valid_code_enables_totp(engineer):
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    c.get(reverse("portal:totp_setup"))  # seeds the session secret
    secret = c.session["pending_totp_secret"]
    code = pyotp.TOTP(secret).now()
    resp = c.post(reverse("portal:totp_setup"), {"code": code})
    # First-time enrolment redirects to the recovery-codes page (shown once).
    assert resp.status_code == 302
    assert resp.url == reverse("portal:recovery_codes")
    engineer.refresh_from_db()
    assert engineer.totp_enabled is True
    assert engineer.get_totp_secret() == secret
    # 10 recovery codes were minted.
    assert engineer.recovery_codes.count() == 10


def test_setup_post_with_wrong_code_does_not_enable(engineer):
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    c.get(reverse("portal:totp_setup"))
    resp = c.post(reverse("portal:totp_setup"), {"code": "000000"})
    assert resp.status_code == 200
    engineer.refresh_from_db()
    assert engineer.totp_enabled is False


def test_setup_without_pending_user_redirects_to_login():
    c = DjangoClient()
    resp = c.get(reverse("portal:totp_setup"))
    assert resp.status_code == 302
    assert resp.url == reverse("portal:login")


# ----- verify ---------------------------------------------------------


def test_verify_post_with_valid_code_completes_login(engineer):
    secret = pyotp.random_base32()
    engineer.set_totp_secret(secret)
    engineer.totp_enabled = True
    engineer.save()
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    code = pyotp.TOTP(secret).now()
    resp = c.post(reverse("portal:totp_verify"), {"code": code})
    assert resp.status_code == 302
    assert "_auth_user_id" in c.session


def test_verify_with_wrong_code_does_not_log_in(engineer):
    secret = pyotp.random_base32()
    engineer.set_totp_secret(secret)
    engineer.totp_enabled = True
    engineer.save()
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    resp = c.post(reverse("portal:totp_verify"), {"code": "000000"})
    assert resp.status_code == 200
    assert "_auth_user_id" not in c.session


# ----- QR endpoint ----------------------------------------------------


def test_qr_returns_svg_for_pending_user(engineer):
    c = DjangoClient()
    c.post(reverse("portal:login"), {"email": "eng@luma.test", "password": "goodpass"})
    c.get(reverse("portal:totp_setup"))
    resp = c.get(reverse("portal:totp_qr"))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/svg+xml"
    assert resp.content.startswith(b"<?xml") or b"<svg" in resp.content[:200]


def test_qr_404s_without_pending_user():
    c = DjangoClient()
    resp = c.get(reverse("portal:totp_qr"))
    assert resp.status_code == 404
