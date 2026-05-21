"""TOTP-aware /api/v1/auth/jwt/create/."""
from __future__ import annotations

import pyotp
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

JWT_URL = "/api/v1/auth/jwt/create/"


@pytest.fixture
def user_no_totp():
    User = get_user_model()
    return User.objects.create_user(
        email="plain@luma.test", password="goodpass", role=User.Role.ENGINEER
    )


@pytest.fixture
def user_with_totp():
    User = get_user_model()
    u = User.objects.create_user(
        email="secured@luma.test", password="goodpass", role=User.Role.ADMIN
    )
    secret = pyotp.random_base32()
    u.set_totp_secret(secret)
    u.totp_enabled = True
    u.save()
    return u, secret


def test_plain_user_gets_tokens_without_totp(user_no_totp):
    resp = APIClient().post(
        JWT_URL, {"email": "plain@luma.test", "password": "goodpass"}, format="json"
    )
    assert resp.status_code == 200
    assert "access" in resp.json() and "refresh" in resp.json()


def test_bad_password_still_401(user_no_totp):
    resp = APIClient().post(
        JWT_URL, {"email": "plain@luma.test", "password": "wrong"}, format="json"
    )
    assert resp.status_code == 401


def test_totp_user_without_code_gets_totp_required(user_with_totp):
    _, _ = user_with_totp
    resp = APIClient().post(
        JWT_URL,
        {"email": "secured@luma.test", "password": "goodpass"},
        format="json",
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "totp_required"


def test_totp_user_with_wrong_code_gets_invalid_totp(user_with_totp):
    resp = APIClient().post(
        JWT_URL,
        {
            "email": "secured@luma.test",
            "password": "goodpass",
            "totp_code": "000000",
        },
        format="json",
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_totp"


def test_totp_user_with_valid_code_gets_tokens(user_with_totp):
    _, secret = user_with_totp
    code = pyotp.TOTP(secret).now()
    resp = APIClient().post(
        JWT_URL,
        {
            "email": "secured@luma.test",
            "password": "goodpass",
            "totp_code": code,
        },
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


# ----- recovery codes ----------------------------------------------------


def test_recovery_code_can_replace_totp_for_login(user_with_totp):
    from accounts.models import RecoveryCode

    user, _ = user_with_totp
    codes = RecoveryCode.regenerate_for(user, count=3)
    resp = APIClient().post(
        JWT_URL,
        {
            "email": "secured@luma.test",
            "password": "goodpass",
            "recovery_code": codes[0],
        },
        format="json",
    )
    assert resp.status_code == 200
    assert "access" in resp.json()


def test_recovery_code_is_single_use(user_with_totp):
    from accounts.models import RecoveryCode

    user, _ = user_with_totp
    codes = RecoveryCode.regenerate_for(user, count=2)
    first = APIClient().post(
        JWT_URL,
        {
            "email": "secured@luma.test",
            "password": "goodpass",
            "recovery_code": codes[0],
        },
        format="json",
    )
    assert first.status_code == 200
    # Replay the same code → invalid_totp.
    second = APIClient().post(
        JWT_URL,
        {
            "email": "secured@luma.test",
            "password": "goodpass",
            "recovery_code": codes[0],
        },
        format="json",
    )
    assert second.status_code == 401
    assert second.json()["detail"] == "invalid_totp"


def test_recovery_code_endpoint_returns_plaintexts(user_with_totp):
    user, secret = user_with_totp
    # Authenticate normally first.
    code = pyotp.TOTP(secret).now()
    login = APIClient().post(
        JWT_URL,
        {"email": "secured@luma.test", "password": "goodpass", "totp_code": code},
        format="json",
    )
    access = login.json()["access"]
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    resp = c.post("/api/v1/auth/recovery-codes/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["codes"]) == 10
    assert body["remaining"] == 10
    # Each code is XXXX-XXXX from the documented alphabet.
    for plain in body["codes"]:
        assert len(plain) == 9 and plain[4] == "-"
