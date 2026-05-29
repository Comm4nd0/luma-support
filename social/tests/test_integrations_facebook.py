"""Facebook Page integration — respx mocks of Graph API responses."""
from __future__ import annotations

import httpx
import pytest
import respx

from social.integrations import SocialFetchResult
from social.integrations.facebook import fetch_for, health_from
from social.models import Platform, SocialAccount

pytestmark = pytest.mark.django_db


# ----- pure health bucketing ------------------------------------------


def test_health_ok_when_both_fields_populated():
    r = SocialFetchResult(followers=100, last_post_at="x")  # type: ignore[arg-type]
    assert health_from(r) == "ok"


def test_health_degraded_when_only_one_populated():
    assert health_from(SocialFetchResult(followers=10, last_post_at=None)) == "degraded"
    assert (
        health_from(SocialFetchResult(followers=None, last_post_at="x"))  # type: ignore[arg-type]
        == "degraded"
    )


def test_health_down_when_both_missing():
    assert health_from(SocialFetchResult()) == "down"


# ----- fetch_for -------------------------------------------------------


def _make_account():
    a = SocialAccount.objects.create(
        platform=Platform.FACEBOOK_PAGE, external_id="999000111"
    )
    a.set_access_token("page-token")
    a.save(update_fields=["access_token_encrypted"])
    return a


@respx.mock
def test_fetch_for_parses_stats_dms_and_comments():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"

    respx.get(f"{base}/999000111").mock(
        return_value=httpx.Response(
            200,
            json={
                "followers_count": 555,
                "fan_count": 540,
                "posts": {
                    "data": [{"created_time": "2026-05-18T10:00:00+0000"}]
                },
            },
        )
    )
    respx.get(f"{base}/999000111/conversations").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "t_1",
                        "updated_time": "2026-05-19T08:00:00+0000",
                        "snippet": "Hi, do you fix mesh wifi?",
                        "participants": {
                            "data": [
                                {"id": "999000111", "name": "Luma"},
                                {"id": "100000123", "name": "Alice Example"},
                            ]
                        },
                    }
                ]
            },
        )
    )
    respx.get(f"{base}/999000111/posts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "p_1",
                        "permalink_url": "https://fb.example/p_1",
                        "comments": {
                            "data": [
                                {
                                    "id": "c_9",
                                    "from": {"id": "200000222", "name": "Bob"},
                                    "message": "love the post",
                                    "created_time": "2026-05-19T07:00:00+0000",
                                    "permalink_url": "https://fb.example/p_1/c_9",
                                }
                            ]
                        },
                    }
                ]
            },
        )
    )

    result = fetch_for(account)
    assert result.followers == 555  # followers_count wins over fan_count
    assert result.last_post_at is not None
    dms = [i for i in result.inbox_items if i.kind == "dm"]
    comments = [i for i in result.inbox_items if i.kind == "comment"]
    assert len(dms) == 1
    assert dms[0].author_display == "Alice Example"
    assert dms[0].author_handle == "100000123"
    assert "Hi, do you fix" in dms[0].preview
    assert len(comments) == 1
    assert comments[0].author_display == "Bob"
    assert comments[0].permalink == "https://fb.example/p_1/c_9"


@respx.mock
def test_fetch_for_falls_back_to_fan_count_when_followers_count_missing():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    respx.get(f"{base}/999000111").mock(
        return_value=httpx.Response(
            200, json={"fan_count": 99, "posts": {"data": []}}
        )
    )
    respx.get(f"{base}/999000111/conversations").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get(f"{base}/999000111/posts").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = fetch_for(account)
    assert result.followers == 99
    assert result.last_post_at is None
    assert result.inbox_items == []


@respx.mock
def test_fetch_for_returns_none_when_stats_4xx():
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    respx.get(f"{base}/999000111").mock(return_value=httpx.Response(400))
    respx.get(f"{base}/999000111/conversations").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get(f"{base}/999000111/posts").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = fetch_for(account)
    assert result.followers is None
    assert result.last_post_at is None


@respx.mock
def test_fetch_for_swallows_inbox_endpoint_failures():
    """A failing conversations / posts endpoint should not blow up the run."""
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    respx.get(f"{base}/999000111").mock(
        return_value=httpx.Response(200, json={"followers_count": 10, "posts": {"data": []}})
    )
    respx.get(f"{base}/999000111/conversations").mock(
        return_value=httpx.Response(403)
    )
    respx.get(f"{base}/999000111/posts").mock(return_value=httpx.Response(500))

    result = fetch_for(account)
    assert result.followers == 10
    assert result.inbox_items == []


@respx.mock
def test_fetch_for_skips_comment_rows_missing_an_id():
    """Defensive: providers occasionally return partial rows."""
    account = _make_account()
    base = "https://graph.facebook.com/v19.0"
    respx.get(f"{base}/999000111").mock(
        return_value=httpx.Response(200, json={"followers_count": 10, "posts": {"data": []}})
    )
    respx.get(f"{base}/999000111/conversations").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    respx.get(f"{base}/999000111/posts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "p_1",
                        "comments": {
                            "data": [
                                {"message": "no id here"},
                                {
                                    "id": "c_ok",
                                    "from": {"id": "x"},
                                    "message": "good",
                                    "created_time": "2026-05-19T07:00:00+0000",
                                },
                            ]
                        },
                    }
                ]
            },
        )
    )

    result = fetch_for(account)
    assert [i.external_id for i in result.inbox_items] == ["c_ok"]
