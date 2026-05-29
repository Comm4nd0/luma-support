"""Instagram Business integration via Meta Graph API (linked Page token)."""
from __future__ import annotations

from datetime import datetime

import httpx

from . import FetchedInboxItem, SocialFetchResult

API = "https://graph.facebook.com/v19.0"


def fetch_for(account) -> SocialFetchResult:
    ig_id = account.external_id
    token = account.get_access_token()  # Page token (Page → linked IG)
    with httpx.Client(base_url=API, timeout=15.0) as client:
        followers, last_post = _profile_stats(client, ig_id, token)
        inbox = _conversations(client, ig_id, token)
        mentions = _recent_media_comments(client, ig_id, token)
    return SocialFetchResult(
        followers=followers,
        last_post_at=last_post,
        kpis={},
        inbox_items=inbox + mentions,
    )


def health_from(result: SocialFetchResult) -> str:
    if result.followers is None and result.last_post_at is None:
        return "down"
    if result.followers is None or result.last_post_at is None:
        return "degraded"
    return "ok"


def _profile_stats(client: httpx.Client, ig_id: str, token: str):
    resp = client.get(
        f"/{ig_id}",
        params={
            "access_token": token,
            "fields": "followers_count,media.limit(1){timestamp,permalink}",
        },
    )
    if resp.status_code >= 400:
        return None, None
    data = resp.json() or {}
    followers = data.get("followers_count")
    media = (data.get("media") or {}).get("data") or []
    last_post = None
    if media:
        ts = media[0].get("timestamp")
        if ts:
            last_post = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return followers, last_post


def _conversations(client: httpx.Client, ig_id: str, token: str):
    resp = client.get(
        f"/{ig_id}/conversations",
        params={
            "access_token": token,
            "platform": "instagram",
            "fields": "id,updated_time,snippet,participants",
            "limit": 25,
        },
    )
    if resp.status_code >= 400:
        return []
    items: list[FetchedInboxItem] = []
    for conv in resp.json().get("data", []) or []:
        cid = conv.get("id") or ""
        updated = conv.get("updated_time")
        ts = (
            datetime.fromisoformat(updated.replace("Z", "+00:00"))
            if updated
            else None
        )
        parts = (conv.get("participants") or {}).get("data") or []
        other = next(
            (p for p in parts if str(p.get("id")) != str(ig_id)),
            {},
        )
        items.append(
            FetchedInboxItem(
                kind="dm",
                external_id=cid,
                author_handle=other.get("username") or str(other.get("id") or ""),
                author_display=other.get("name") or "",
                preview=(conv.get("snippet") or "")[:500],
                permalink=f"https://www.instagram.com/direct/t/{cid}/",
                received_at=ts,
            )
        )
    return items


def _recent_media_comments(client: httpx.Client, ig_id: str, token: str):
    resp = client.get(
        f"/{ig_id}/media",
        params={
            "access_token": token,
            "fields": "id,permalink,comments.limit(10){id,username,text,timestamp}",
            "limit": 5,
        },
    )
    if resp.status_code >= 400:
        return []
    items: list[FetchedInboxItem] = []
    for media in resp.json().get("data", []) or []:
        for c in (media.get("comments") or {}).get("data", []) or []:
            cid = c.get("id") or ""
            if not cid:
                continue
            ts_raw = c.get("timestamp")
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if ts_raw else None
            items.append(
                FetchedInboxItem(
                    kind="comment",
                    external_id=cid,
                    author_handle=c.get("username") or "",
                    author_display="",
                    preview=(c.get("text") or "")[:500],
                    permalink=media.get("permalink") or "",
                    received_at=ts,
                )
            )
    return items
