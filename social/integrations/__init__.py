"""Per-platform fetchers for Luma's social accounts.

Each integration exposes:

    fetch_for(account) -> SocialFetchResult
    health_from(result) -> str  # "ok" | "degraded" | "down"

`fetch_for` reads `account.access_token_encrypted` (decrypting via
`clients.encryption`) and the provider config from settings. It hits the
platform's public API and returns a normalised `SocialFetchResult`.
Exceptions bubble up to the refresh task, which records a short
`last_error` and flips `health_status` to "down" — never log raw URLs
with token query params.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FetchedInboxItem:
    """Normalised inbox item from any platform — DM, mention, or comment."""

    kind: str  # "dm" | "mention" | "comment"
    external_id: str
    author_handle: str = ""
    author_display: str = ""
    preview: str = ""
    permalink: str = ""
    received_at: datetime | None = None


@dataclass
class SocialFetchResult:
    followers: int | None = None
    last_post_at: datetime | None = None
    kpis: dict[str, Any] = field(default_factory=dict)
    inbox_items: list[FetchedInboxItem] = field(default_factory=list)
    # If a sub-feature was skipped because of missing scope / app review,
    # the integration records a short message here; the refresh task
    # surfaces it as `SocialAccount.last_error` without flipping health
    # away from "ok".
    partial_reason: str = ""


def redact_error(exc: Exception) -> str:
    """Short, token-safe summary of an HTTP / parse error for `last_error`."""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        return f"{exc.response.status_code}: {exc.response.reason_phrase or 'http error'}"
    if isinstance(exc, httpx.RequestError):
        return f"transport: {exc.__class__.__name__}"
    msg = str(exc) or exc.__class__.__name__
    return msg[:200]
