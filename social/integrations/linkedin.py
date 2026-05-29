"""LinkedIn Page integration.

v1 scope: Page follower count, latest post timestamp, and Page
mentions/comments. DM ingestion requires the LinkedIn Marketing
Developer Platform tier (Messaging API) — we leave `inbox_items` empty
for DMs and surface `partial_reason` when that's the case.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from . import FetchedInboxItem, SocialFetchResult

API = "https://api.linkedin.com"


def fetch_for(account) -> SocialFetchResult:
    org_urn = account.external_id  # e.g. "urn:li:organization:12345"
    token = account.get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    with httpx.Client(base_url=API, headers=headers, timeout=15.0) as client:
        followers = _followers(client, org_urn)
        last_post_at, post_urns = _recent_posts(client, org_urn)
        mentions = _mentions_from_comments(client, post_urns)

    return SocialFetchResult(
        followers=followers,
        last_post_at=last_post_at,
        kpis={},
        inbox_items=mentions,
        partial_reason=(
            "DMs not ingested — LinkedIn Messaging requires Marketing Developer Platform"
        ),
    )


def health_from(result: SocialFetchResult) -> str:
    """Bucket the result.

    Followers fetched OK → at least degraded; a successful posts fetch
    on top → ok; both endpoints failed → down (the caller catches
    exceptions before we get here, so reaching this fn means at least
    one succeeded).
    """
    if result.followers is None and result.last_post_at is None:
        return "down"
    if result.followers is None or result.last_post_at is None:
        return "degraded"
    return "ok"


def _followers(client: httpx.Client, org_urn: str) -> int | None:
    resp = client.get(
        "/v2/networkSizes/" + org_urn,
        params={"edgeType": "CompanyFollowedByMember"},
    )
    if resp.status_code >= 400:
        return None
    return int(resp.json().get("firstDegreeSize") or 0)


def _recent_posts(client: httpx.Client, org_urn: str):
    """Return (latest post datetime, list of post URNs from this page)."""
    resp = client.get(
        "/v2/posts",
        params={"q": "author", "author": org_urn, "count": 20},
    )
    if resp.status_code >= 400:
        return None, []
    elements = resp.json().get("elements", []) or []
    if not elements:
        return None, []
    timestamps = []
    urns = []
    for el in elements:
        ts = el.get("publishedAt") or el.get("createdAt") or 0
        if ts:
            timestamps.append(int(ts))
        urn = el.get("id") or el.get("urn")
        if urn:
            urns.append(urn)
    latest = max(timestamps) if timestamps else None
    return (
        datetime.fromtimestamp(latest / 1000, tz=UTC) if latest else None,
        urns,
    )


def _mentions_from_comments(client: httpx.Client, post_urns: list[str]):
    items: list[FetchedInboxItem] = []
    for urn in post_urns[:5]:  # cap fan-out to avoid rate-limit storms
        resp = client.get(f"/v2/socialActions/{urn}/comments", params={"count": 20})
        if resp.status_code >= 400:
            continue
        for c in resp.json().get("elements", []) or []:
            cid = c.get("id") or ""
            if not cid:
                continue
            actor = c.get("actor", "")
            created = int((c.get("created") or {}).get("time", 0)) or 0
            items.append(
                FetchedInboxItem(
                    kind="comment",
                    external_id=cid,
                    author_handle=actor,
                    author_display="",
                    preview=(c.get("message") or {}).get("text", "")[:500],
                    permalink=f"https://www.linkedin.com/feed/update/{urn}/",
                    received_at=(
                        datetime.fromtimestamp(created / 1000, tz=UTC)
                        if created
                        else None
                    ),
                )
            )
    return items
