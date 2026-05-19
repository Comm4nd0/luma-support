"""Instagram Business integration — respx mocks of Graph API responses."""
from __future__ import annotations

import httpx
import pytest
import respx

from social.integrations import SocialFetchResult
from social.integrations.instagram import fetch_for, health_from
from social.models import Platform, SocialAccount

pytestmark = pytest.mark.django_db


# ----- pure health bucketing ------------------------------------------


def test_health_ok():
    assert health_from(SocialFetchResult(followers=1, last_post_at="x")) == "ok"  # type: ignore[arg-type]


def test_health_degraded_when_one_missing():
    assert (
        health_from(SocialFetchResult(followers=1, last_post_at=None)) == "degraded"
    )
    assert (
        health_from(SocialFetchResult(followers=None, last_post_at="x"))  # type: ignore[arg-type]
        == "degraded"
    )


def test_health_down_when_both_missing():
    assert health_from(SocialFetchResult()) == "down"


# ----- fetch_for -------------------------------------------------------


def _make_account():
    a = SocialAccount.objects.create(
        platform=Platform.INSTAGRAM_BUSINESS, external_id="17841400000000000"
    )
    # IG Business uses the linked FB Page token.
    a.set_access_token("page-token")
    a.save(update_fields=["access_token_encrypted"])
    return a


@respx.mock
def test_fetch_for_parses_profile_dms_and_media_comments():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    ig = account.external_id

    respx.get(f"{base}/{ig}").mock(
        return_value=httpx.Response(
            200,
            json={
                "followers_count": 4200,
                "media": {
                    "data": [
                        {
                            "timestamp": "2026-05-18T14:00:00+0000",
                            "permalink": "https://instagram.com/p/abc/",
                        }
                    ]
                },
            },
        )
    )
    respx.get(f"{base}/{ig}/conversations").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "ig_t_1",
                        "updated_time": "2026-05-19T09:00:00+0000",
                        "snippet": "what do you charge for cctv?",
                        "participants": {
                            "data": [
                                {"id": ig, "name": "Luma"},
                                {
                                    "id": "200000333",
                                    "username": "carol_example",
                                    "name": "Carol Example",
                                },
                            ]
                        },
                    }
                ]
            },
        )
    )
    respx.get(f"{base}/{ig}/media").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "m_1",
                        "permalink": "https://instagram.com/p/m_1/",
                        "comments": {
                            "data": [
                                {
                                    "id": "ig_c_5",
                                    "username": "dave",
                                    "text": "nice install",
                                    "timestamp": "2026-05-19T06:00:00+0000",
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )

    result = fetch_for(account)
    assert result.followers == 4200
    assert result.last_post_at is not None
    dms = [i for i in result.inbox_items if i.kind == "dm"]
    comments = [i for i in result.inbox_items if i.kind == "comment"]
    assert len(dms) == 1
    assert dms[0].author_handle == "carol_example"  # IG: prefers username
    assert dms[0].permalink == "https://www.instagram.com/direct/t/ig_t_1/"
    assert len(comments) == 1
    assert comments[0].author_handle == "dave"
    assert comments[0].permalink == "https://instagram.com/p/m_1/"


@respx.mock
def test_fetch_for_handles_403_on_profile():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    ig = account.external_id
    respx.get(f"{base}/{ig}").mock(return_value=httpx.Response(403))
    respx.get(f"{base}/{ig}/conversations").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get(f"{base}/{ig}/media").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = fetch_for(account)
    assert result.followers is None
    assert result.last_post_at is None
    assert result.inbox_items == []


@respx.mock
def test_fetch_for_falls_back_to_user_id_when_username_missing():
    """If a participant has no username (private DM source) we use the id."""
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    ig = account.external_id
    respx.get(f"{base}/{ig}").mock(
        return_value=httpx.Response(200, json={"followers_count": 1, "media": {"data": []}})
    )
    respx.get(f"{base}/{ig}/conversations").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "ig_t_2",
                        "updated_time": "2026-05-19T09:00:00+0000",
                        "snippet": "hi",
                        "participants": {
                            "data": [
                                {"id": ig},
                                {"id": "anon-1"},
                            ]
                        },
                    }
                ]
            },
        )
    )
    respx.get(f"{base}/{ig}/media").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = fetch_for(account)
    [item] = result.inbox_items
    assert item.author_handle == "anon-1"


@respx.mock
def test_fetch_for_swallows_inbox_endpoint_failures():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    ig = account.external_id
    respx.get(f"{base}/{ig}").mock(
        return_value=httpx.Response(200, json={"followers_count": 1, "media": {"data": []}})
    )
    respx.get(f"{base}/{ig}/conversations").mock(return_value=httpx.Response(500))
    respx.get(f"{base}/{ig}/media").mock(return_value=httpx.Response(500))

    result = fetch_for(account)
    assert result.followers == 1
    assert result.inbox_items == []
