"""OAuth helpers for the three platforms.

Each platform follows the same shape:

    authorize_url(platform, state) -> URL string
    exchange_code(platform, code) -> {"access_token", "refresh_token"?,
                                       "expires_in"?, "scope"?, "external_id"?,
                                       "display_name"?, "avatar_url"?}

LinkedIn:
  - OIDC + organisation scope. Access tokens last ~60 days; refresh
    tokens are only issued under the Marketing Developer Platform tier,
    so the model stores `token_expires_at` and the refresh task surfaces
    an alert at T-7d. We do NOT attempt silent refresh outside MDP.

Meta (Facebook Page + Instagram Business):
  - Standard FB Login. We exchange a short-lived user token for a
    long-lived (~60d) user token, then call `/me/accounts` to enumerate
    pages and grab a **non-expiring** Page token per Page. Instagram
    Business accounts are reached via their linked Page token.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core import signing

from .models import Platform

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_ORGS_URL = (
    "https://api.linkedin.com/v2/organizationAcls"
    "?q=roleAssignee&role=ADMINISTRATOR&projection=(elements*(organization~(id,localizedName,vanityName,logoV2)))"
)

META_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
META_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
META_ACCOUNTS_URL = "https://graph.facebook.com/v19.0/me/accounts"

_STATE_SALT = "social.oauth.state"
_STATE_MAX_AGE_S = 600  # 10 minutes


def sign_state(user_pk: int, platform: str) -> str:
    """Return a signed, timestamped state token bound to (user, platform)."""
    return signing.TimestampSigner(salt=_STATE_SALT).sign(f"{user_pk}:{platform}")


def verify_state(state: str, user_pk: int, platform: str) -> bool:
    try:
        value = signing.TimestampSigner(salt=_STATE_SALT).unsign(
            state, max_age=_STATE_MAX_AGE_S
        )
    except signing.BadSignature:
        return False
    return value == f"{user_pk}:{platform}"


def authorize_url(platform: str, state: str) -> str:
    if platform == Platform.LINKEDIN_PAGE:
        params = {
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "scope": settings.LINKEDIN_SCOPES,
            "state": state,
        }
        return f"{LINKEDIN_AUTH_URL}?{urlencode(params)}"
    if platform in (Platform.FACEBOOK_PAGE, Platform.INSTAGRAM_BUSINESS):
        params = {
            "response_type": "code",
            "client_id": settings.META_APP_ID,
            "redirect_uri": settings.META_REDIRECT_URI,
            "scope": settings.META_SCOPES,
            "state": state,
        }
        return f"{META_AUTH_URL}?{urlencode(params)}"
    raise ValueError(f"unsupported platform: {platform}")


def exchange_code_linkedin(code: str) -> dict:
    """LinkedIn: code → access token + lightweight profile + page IDs."""
    resp = httpx.post(
        LINKEDIN_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    tok = resp.json()
    access = tok["access_token"]
    expires_in = int(tok.get("expires_in") or 0)
    scope = tok.get("scope", "")

    orgs = httpx.get(
        LINKEDIN_ORGS_URL,
        headers={"Authorization": f"Bearer {access}"},
        timeout=15.0,
    )
    orgs.raise_for_status()
    pages = []
    for el in orgs.json().get("elements", []):
        org = el.get("organization~") or {}
        pages.append(
            {
                "external_id": f"urn:li:organization:{org.get('id')}",
                "display_name": org.get("localizedName", ""),
                "avatar_url": "",
            }
        )
    return {
        "access_token": access,
        "refresh_token": tok.get("refresh_token", ""),
        "expires_at": _expires_at(expires_in),
        "scope": scope,
        "pages": pages,
    }


def exchange_code_meta(code: str) -> dict:
    """Meta: short-lived → long-lived user token → per-Page tokens.

    Returns one entry per managed Page in `pages`; the caller decides
    whether each one is to be persisted as a Facebook Page connection,
    an Instagram Business connection (via `ig_business_id`), or both.
    """
    short = httpx.get(
        META_TOKEN_URL,
        params={
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.META_REDIRECT_URI,
            "code": code,
        },
        timeout=15.0,
    )
    short.raise_for_status()
    short_token = short.json()["access_token"]

    long_ = httpx.get(
        META_TOKEN_URL,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=15.0,
    )
    long_.raise_for_status()
    long_payload = long_.json()
    user_token = long_payload["access_token"]
    expires_in = int(long_payload.get("expires_in") or 0)

    accounts = httpx.get(
        META_ACCOUNTS_URL,
        params={
            "access_token": user_token,
            "fields": (
                "id,name,access_token,instagram_business_account{id,username,profile_picture_url},picture"
            ),
        },
        timeout=15.0,
    )
    accounts.raise_for_status()
    pages = []
    for p in accounts.json().get("data", []):
        ig = p.get("instagram_business_account") or {}
        pages.append(
            {
                "page_id": p["id"],
                "page_name": p.get("name", ""),
                "page_token": p.get("access_token", ""),
                "page_avatar": ((p.get("picture") or {}).get("data") or {}).get("url", ""),
                "ig_business_id": ig.get("id") or "",
                "ig_username": ig.get("username") or "",
                "ig_avatar": ig.get("profile_picture_url") or "",
            }
        )
    return {
        "user_token": user_token,
        "user_token_expires_at": _expires_at(expires_in),
        "pages": pages,
    }


def _expires_at(seconds: int):
    if not seconds:
        return None
    return datetime.now(tz=UTC) + timedelta(seconds=seconds)
