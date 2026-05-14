"""Xero OAuth 2.0 helpers — authorize URL, code exchange, refresh."""
from __future__ import annotations

from urllib.parse import urlencode

import httpx
from django.conf import settings

AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"


def authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.XERO_CLIENT_ID,
        "redirect_uri": settings.XERO_REDIRECT_URI,
        "scope": settings.XERO_SCOPES,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Swap an authorization code for an access + refresh token."""
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.XERO_REDIRECT_URI,
        },
        auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def refresh(refresh_token: str) -> dict:
    """Refresh an access token. Xero rotates the refresh token on every call."""
    resp = httpx.post(
        TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def list_connections(access_token: str) -> list[dict]:
    resp = httpx.get(
        CONNECTIONS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()
