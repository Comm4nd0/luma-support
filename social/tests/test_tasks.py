"""Refresh task: health transitions, inbox upsert, overdue alerts."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from notifications.models import Notification
from social.integrations import FetchedInboxItem, SocialFetchResult
from social.models import (
    InboxStatus,
    Platform,
    SocialAccount,
    SocialInboxItem,
)
from social.tasks import refresh_social_accounts


@pytest.fixture
def linkedin_account(db, admin_user):
    account = SocialAccount.objects.create(
        platform=Platform.LINKEDIN_PAGE,
        external_id="urn:li:org:1",
        display_name="Luma",
        health_status="ok",
        connected_by=admin_user,
    )
    account.set_access_token("token")
    account.save()
    return account


@pytest.mark.django_db
def test_refresh_applies_result_and_persists_inbox(linkedin_account, engineer_user):
    now = timezone.now()
    result = SocialFetchResult(
        followers=500,
        last_post_at=now - timedelta(hours=2),
        kpis={"impressions_7d": 1234},
        inbox_items=[
            FetchedInboxItem(
                kind="comment",
                external_id="c-1",
                author_handle="@alice",
                preview="hi there",
                permalink="https://example.com/c-1",
                received_at=now - timedelta(minutes=5),
            )
        ],
    )
    with patch(
        "social.integrations.linkedin.fetch_for", return_value=result
    ), patch(
        "social.integrations.linkedin.health_from", return_value="ok"
    ):
        refresh_social_accounts()

    linkedin_account.refresh_from_db()
    assert linkedin_account.followers == 500
    assert linkedin_account.last_post_at is not None
    assert linkedin_account.kpis_json["impressions_7d"] == 1234
    assert linkedin_account.health_status == "ok"
    assert SocialInboxItem.objects.filter(
        account=linkedin_account, external_id="c-1"
    ).exists()


@pytest.mark.django_db
def test_refresh_fans_out_social_alert_on_health_transition(
    linkedin_account, engineer_user
):
    """Fresh transition away from ok creates one notification per active staff user."""
    result = SocialFetchResult(followers=None, last_post_at=None)
    with patch(
        "social.integrations.linkedin.fetch_for", return_value=result
    ), patch(
        "social.integrations.linkedin.health_from", return_value="down"
    ):
        refresh_social_accounts()

    linkedin_account.refresh_from_db()
    assert linkedin_account.health_status == "down"
    alerts = Notification.objects.filter(
        type=Notification.Type.SOCIAL_ALERT
    )
    # engineer_user + the admin who connected it; both are active staff.
    assert alerts.count() >= 2


@pytest.mark.django_db
def test_refresh_does_not_realert_on_same_health(linkedin_account, engineer_user):
    """Two consecutive 'down' refreshes only emit one alert."""
    result = SocialFetchResult(followers=None, last_post_at=None)
    with patch(
        "social.integrations.linkedin.fetch_for", return_value=result
    ), patch(
        "social.integrations.linkedin.health_from", return_value="down"
    ):
        refresh_social_accounts()
        first_count = Notification.objects.filter(
            type=Notification.Type.SOCIAL_ALERT
        ).count()
        refresh_social_accounts()
        second_count = Notification.objects.filter(
            type=Notification.Type.SOCIAL_ALERT
        ).count()

    assert second_count == first_count


@pytest.mark.django_db
def test_refresh_records_redacted_error_on_exception(linkedin_account, engineer_user):
    with patch(
        "social.integrations.linkedin.fetch_for", side_effect=RuntimeError("boom")
    ):
        refresh_social_accounts()

    linkedin_account.refresh_from_db()
    assert linkedin_account.health_status == "down"
    assert linkedin_account.last_error
    assert "token" not in linkedin_account.last_error.lower()


@pytest.mark.django_db
def test_overdue_alert_fires_once_then_dedupes(linkedin_account, engineer_user):
    """An inbox item older than 24h triggers SOCIAL_ALERT; subsequent runs are deduped."""
    now = timezone.now()
    SocialInboxItem.objects.create(
        account=linkedin_account,
        kind="dm",
        external_id="m-old",
        received_at=now - timedelta(hours=30),
        status=InboxStatus.OPEN,
    )
    result = SocialFetchResult(followers=10, last_post_at=now - timedelta(hours=1))
    with patch(
        "social.integrations.linkedin.fetch_for", return_value=result
    ), patch(
        "social.integrations.linkedin.health_from", return_value="ok"
    ):
        refresh_social_accounts()
        first = Notification.objects.filter(
            type=Notification.Type.SOCIAL_ALERT
        ).count()
        refresh_social_accounts()
        second = Notification.objects.filter(
            type=Notification.Type.SOCIAL_ALERT
        ).count()

    assert first >= 2  # admin + engineer
    assert second == first  # dedup window suppresses a re-alert


@pytest.mark.django_db
def test_refresh_updates_dismissed_item_without_resurrecting(
    linkedin_account, engineer_user
):
    now = timezone.now()
    item = SocialInboxItem.objects.create(
        account=linkedin_account,
        kind="comment",
        external_id="c-1",
        received_at=now - timedelta(hours=1),
        preview="original",
        status=InboxStatus.DISMISSED,
    )
    result = SocialFetchResult(
        followers=10,
        last_post_at=now - timedelta(hours=1),
        inbox_items=[
            FetchedInboxItem(
                kind="comment",
                external_id="c-1",
                preview="edited by author",
                received_at=now,
            )
        ],
    )
    with patch(
        "social.integrations.linkedin.fetch_for", return_value=result
    ), patch(
        "social.integrations.linkedin.health_from", return_value="ok"
    ):
        refresh_social_accounts()

    item.refresh_from_db()
    assert item.status == InboxStatus.DISMISSED
    assert item.preview == "edited by author"
