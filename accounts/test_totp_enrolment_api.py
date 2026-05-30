"""Mobile TOTP self-enrolment API: /auth/totp/setup/ + /auth/totp/confirm/."""
import pyotp
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def engineer():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email="enrol@luma.test", password="goodpass", role=User.Role.ENGINEER
    )


def test_setup_returns_secret_and_uri_without_enabling(engineer):
    c = APIClient()
    c.force_authenticate(engineer)
    resp = c.post("/api/v1/auth/totp/setup/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["secret"]
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    engineer.refresh_from_db()
    assert engineer.totp_enabled is False  # not enabled until confirmed
    assert engineer.get_totp_secret() == body["secret"]


def test_confirm_with_valid_code_enables_and_returns_recovery_codes(engineer):
    c = APIClient()
    c.force_authenticate(engineer)
    secret = c.post("/api/v1/auth/totp/setup/").json()["secret"]
    code = pyotp.TOTP(secret).now()
    resp = c.post("/api/v1/auth/totp/confirm/", {"code": code}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert len(body["recovery_codes"]) > 0
    engineer.refresh_from_db()
    assert engineer.totp_enabled is True


def test_confirm_with_bad_code_does_not_enable(engineer):
    c = APIClient()
    c.force_authenticate(engineer)
    c.post("/api/v1/auth/totp/setup/")
    resp = c.post("/api/v1/auth/totp/confirm/", {"code": "000000"}, format="json")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_totp"
    engineer.refresh_from_db()
    assert engineer.totp_enabled is False


def test_setup_refused_once_enabled(engineer):
    engineer.totp_enabled = True
    engineer.save(update_fields=["totp_enabled"])
    c = APIClient()
    c.force_authenticate(engineer)
    resp = c.post("/api/v1/auth/totp/setup/")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "totp_already_enabled"


def test_setup_requires_auth():
    resp = APIClient().post("/api/v1/auth/totp/setup/")
    assert resp.status_code in (401, 403)
