"""Facebook Page integration via Meta Graph API."""
from __future__ import annotations

from datetime import datetime

import httpx

from . import FetchedInboxItem, SocialFetchResult

API = "https://graph.facebook.com/v19.0"


def fetch_for(account) -> SocialFetchResult:
    page_id = account.external_id
    token = account.get_access_token()
    with httpx.Client(base_url=API, timeout=15.0) as client:
        followers, last_post = _page_stats(client, page_id, token)
        inbox = _conversations(client, page_id, token)
        mentions = _post_comments(client, page_id, token)
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


def _page_stats(client: httpx.Client, page_id: str, token: str):
    resp = client.get(
        f"/{page_id}",
        params={
            "access_token": token,
            "fields": "followers_count,fan_count,posts.limit(1){created_time}",
        },
    )
    if resp.status_code >= 400:
        return None, None
    data = resp.json() or {}
    followers = data.get("followers_count") or data.get("fan_count")
    posts = (data.get("posts") or {}).get("data") or []
    last_post = None
    if posts:
        ct = posts[0].get("created_time")
        if ct:
            last_post = datetime.fromisoformat(ct.replace("Z", "+00:00"))
    return followers, last_post


def _conversations(client: httpx.Client, page_id: str, token: str):
    resp = client.get(
        f"/{page_id}/conversations",
        params={
            "access_token": token,
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
        # The Page is one participant; pick the other as the author.
        other = next(
            (p for p in parts if str(p.get("id")) != str(page_id)),
            {},
        )
        items.append(
            FetchedInboxItem(
                kind="dm",
                external_id=cid,
                author_handle=str(other.get("id") or ""),
                author_display=other.get("name") or "",
                preview=(conv.get("snippet") or "")[:500],
                permalink=f"https://business.facebook.com/latest/inbox/all/?asset_id={page_id}&thread_id={cid}",
                received_at=ts,
            )
        )
    return items


def _post_comments(client: httpx.Client, page_id: str, token: str):
    resp = client.get(
        f"/{page_id}/posts",
        params={
            "access_token": token,
            "fields": "id,permalink_url,comments.limit(10){id,from,message,created_time,permalink_url}",  # noqa: E501
            "limit": 5,
        },
    )
    if resp.status_code >= 400:
        return []
    items: list[FetchedInboxItem] = []
    for post in resp.json().get("data", []) or []:
        for c in (post.get("comments") or {}).get("data", []) or []:
            cid = c.get("id") or ""
            if not cid:
                continue
            ct = c.get("created_time")
            ts = datetime.fromisoformat(ct.replace("Z", "+00:00")) if ct else None
            frm = c.get("from") or {}
            items.append(
                FetchedInboxItem(
                    kind="comment",
                    external_id=cid,
                    author_handle=str(frm.get("id") or ""),
                    author_display=frm.get("name") or "",
                    preview=(c.get("message") or "")[:500],
                    permalink=c.get("permalink_url")
                    or post.get("permalink_url")
                    or "",
                    received_at=ts,
                )
            )
    return items
