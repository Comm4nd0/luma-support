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
