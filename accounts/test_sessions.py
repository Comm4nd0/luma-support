"""Session list / revoke endpoints (powered by SimpleJWT blacklist)."""
import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _login(user):
    """Authenticate, returning the access + refresh tokens issued."""
    c = APIClient()
    resp = c.post(
        "/api/v1/auth/jwt/create/",
        {"email": user.email, "password": "goodpass"},
        format="json",
    )
    return resp.json()


def _user(**kwargs):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email=kwargs.pop("email", "s@luma.test"),
        password=kwargs.pop("password", "goodpass"),
        role=kwargs.pop("role", User.Role.ENGINEER),
        **kwargs,
    )


def test_login_creates_outstanding_token():
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    u = _user()
    _login(u)
    assert OutstandingToken.objects.filter(user=u).count() == 1


def test_list_sessions_returns_outstanding_tokens():
    u = _user()
    tokens = _login(u)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = c.get("/api/v1/auth/sessions/")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) >= 1


def test_revoke_session_blacklists_the_token():
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    u = _user()
    tokens = _login(u)
    sess = OutstandingToken.objects.get(user=u)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = c.post(f"/api/v1/auth/sessions/{sess.pk}/revoke/")
    assert resp.status_code == 200
    assert BlacklistedToken.objects.filter(token=sess).exists()


def test_revoke_all_blacklists_every_session():
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    u = _user()
    _login(u)
    _login(u)
    tokens = _login(u)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    resp = c.post("/api/v1/auth/sessions/revoke-all/")
    assert resp.status_code == 200
    # All three of this user's outstanding tokens should now be on
    # the blacklist.
    assert BlacklistedToken.objects.filter(token__user=u).count() == 3


def test_other_users_session_cannot_be_revoked():
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    a = _user(email="a@luma.test")
    b = _user(email="b@luma.test")
    _login(a)
    b_tok = _login(b)
    a_sess = OutstandingToken.objects.get(user=a)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {b_tok['access']}")
    resp = c.post(f"/api/v1/auth/sessions/{a_sess.pk}/revoke/")
    assert resp.status_code == 404


# ----- portal (server-rendered) sessions page — web/mobile parity ------


def test_portal_sessions_page_lists_outstanding_tokens(django_user_model):
    from django.test import Client as DjangoClient

    u = _user()
    _login(u)  # mints one outstanding refresh token
    c = DjangoClient()
    c.force_login(u)
    resp = c.get("/sessions/")
    assert resp.status_code == 200
    assert len(resp.context["sessions"]) == 1


def test_portal_sessions_revoke_blacklists_one_token():
    from django.test import Client as DjangoClient
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    u = _user()
    _login(u)
    sess = OutstandingToken.objects.get(user=u)
    c = DjangoClient()
    c.force_login(u)
    resp = c.post("/sessions/", {"action": "revoke", "session_id": sess.pk})
    assert resp.status_code == 302
    assert BlacklistedToken.objects.filter(token=sess).exists()


def test_portal_sessions_revoke_all_blacklists_every_token():
    from django.test import Client as DjangoClient
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    u = _user()
    _login(u)
    _login(u)
    c = DjangoClient()
    c.force_login(u)
    resp = c.post("/sessions/", {"action": "revoke_all"})
    assert resp.status_code == 302
    assert BlacklistedToken.objects.filter(token__user=u).count() == 2


def test_portal_sessions_cannot_revoke_another_users_token():
    from django.test import Client as DjangoClient
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    a = _user(email="a@luma.test")
    b = _user(email="b@luma.test")
    _login(a)
    a_sess = OutstandingToken.objects.get(user=a)
    c = DjangoClient()
    c.force_login(b)
    c.post("/sessions/", {"action": "revoke", "session_id": a_sess.pk})
    assert not BlacklistedToken.objects.filter(token=a_sess).exists()
