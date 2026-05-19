"""LinkedIn integration — wire-level tests with respx httpx mocks."""
from __future__ import annotations

import re

import httpx
import pytest
import respx

from social.integrations import SocialFetchResult
from social.integrations.linkedin import fetch_for, health_from
from social.models import Platform, SocialAccount

pytestmark = pytest.mark.django_db


# ----- pure health bucketing ------------------------------------------


def test_health_ok_when_both_fields_populated():
    r = SocialFetchResult(followers=100, last_post_at="anything-truthy")  # type: ignore[arg-type]
    assert health_from(r) == "ok"


def test_health_degraded_when_only_one_populated():
    only_followers = SocialFetchResult(followers=100, last_post_at=None)
    only_posts = SocialFetchResult(followers=None, last_post_at="x")  # type: ignore[arg-type]
    assert health_from(only_followers) == "degraded"
    assert health_from(only_posts) == "degraded"


def test_health_down_when_both_missing():
    assert health_from(SocialFetchResult()) == "down"


# ----- fetch_for happy path -------------------------------------------


def _make_account():
    a = SocialAccount.objects.create(
        platform=Platform.LINKEDIN_PAGE, external_id="urn:li:organization:42"
    )
    a.set_access_token("li-token")
    a.save(update_fields=["access_token_encrypted"])
    return a


@respx.mock
def test_fetch_for_parses_followers_posts_and_comments():
    account = _make_account()
    respx.get(
        "https://api.linkedin.com/v2/networkSizes/urn:li:organization:42"
    ).mock(return_value=httpx.Response(200, json={"firstDegreeSize": 1234}))

    respx.get("https://api.linkedin.com/v2/posts").mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {"id": "urn:li:share:1", "publishedAt": 1700000000000},
                    {"id": "urn:li:share:2", "publishedAt": 1710000000000},
                ]
            },
        )
    )
    # Comments are fetched per post URN; respx route matches by base URL
    # so a single mock covers both calls.
    respx.get(
        re.compile(r"https://api\.linkedin\.com/v2/socialActions/.+/comments")
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "id": "urn:li:comment:99",
                        "actor": "urn:li:person:alice",
                        "created": {"time": 1709999000000},
                        "message": {"text": "hello there"},
                    }
                ]
            },
        )
    )

    result = fetch_for(account)
    assert result.followers == 1234
    assert result.last_post_at is not None
    # Comments returned across both posts (same mock returns the same list each call).
    assert len(result.inbox_items) >= 1
    first = result.inbox_items[0]
    assert first.kind == "comment"
    assert first.external_id == "urn:li:comment:99"
    assert first.preview == "hello there"
    assert "DMs not ingested" in result.partial_reason


@respx.mock
def test_fetch_for_returns_none_when_followers_endpoint_403s():
    account = _make_account()
    respx.get(
        "https://api.linkedin.com/v2/networkSizes/urn:li:organization:42"
    ).mock(return_value=httpx.Response(403, json={"message": "forbidden"}))
    respx.get("https://api.linkedin.com/v2/posts").mock(
        return_value=httpx.Response(200, json={"elements": []})
    )

    result = fetch_for(account)
    assert result.followers is None
    # No posts → last_post_at is None and post_urns is empty so no comment
    # fetches happen.
    assert result.last_post_at is None
    assert result.inbox_items == []


@respx.mock
def test_fetch_for_skips_comments_when_posts_endpoint_403s():
    account = _make_account()
    respx.get(
        "https://api.linkedin.com/v2/networkSizes/urn:li:organization:42"
    ).mock(return_value=httpx.Response(200, json={"firstDegreeSize": 10}))
    respx.get("https://api.linkedin.com/v2/posts").mock(
        return_value=httpx.Response(403)
    )

    result = fetch_for(account)
    assert result.followers == 10
    assert result.last_post_at is None
    assert result.inbox_items == []


@respx.mock
def test_fetch_for_caps_comment_fan_out_to_five_posts():
    """If a Page has many recent posts we only walk the top 5 for comments."""
    account = _make_account()
    respx.get(
        "https://api.linkedin.com/v2/networkSizes/urn:li:organization:42"
    ).mock(return_value=httpx.Response(200, json={"firstDegreeSize": 1}))
    respx.get("https://api.linkedin.com/v2/posts").mock(
        return_value=httpx.Response(
            200,
            json={
                "elements": [
                    {"id": f"urn:li:share:{i}", "publishedAt": 1700000000000 + i}
                    for i in range(20)
                ]
            },
        )
    )
    route = respx.get(
        re.compile(r"https://api\.linkedin\.com/v2/socialActions/.+/comments")
    ).mock(return_value=httpx.Response(200, json={"elements": []}))

    fetch_for(account)
    assert route.call_count == 5
