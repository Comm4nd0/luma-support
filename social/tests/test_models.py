"""Model-level behaviour for SocialAccount + SocialInboxItem."""
from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from social.models import (
    InboxStatus,
    Platform,
    SocialAccount,
    SocialInboxItem,
)


@pytest.mark.django_db
def test_set_get_access_token_round_trips():
    account = SocialAccount.objects.create(
        platform=Platform.LINKEDIN_PAGE, external_id="urn:li:org:1"
    )
    account.set_access_token("super-secret")
    account.save()

    reloaded = SocialAccount.objects.get(pk=account.pk)
    assert reloaded.get_access_token() == "super-secret"
    assert reloaded.access_token_encrypted != "super-secret"


@pytest.mark.django_db
def test_platform_external_id_is_unique():
    SocialAccount.objects.create(
        platform=Platform.LINKEDIN_PAGE, external_id="urn:li:org:1"
    )
    with pytest.raises(IntegrityError):
        SocialAccount.objects.create(
            platform=Platform.LINKEDIN_PAGE, external_id="urn:li:org:1"
        )


@pytest.mark.django_db
def test_followers_delta_and_days_since_last_post():
    account = SocialAccount.objects.create(
        platform=Platform.FACEBOOK_PAGE,
        external_id="123",
        followers=120,
        followers_7d_ago=100,
        last_post_at=timezone.now() - timedelta(days=3),
    )
    assert account.followers_delta_7d == 20
    assert account.days_since_last_post == 3


@pytest.mark.django_db
def test_inbox_item_unique_per_account_external():
    account = SocialAccount.objects.create(
        platform=Platform.INSTAGRAM_BUSINESS, external_id="ig-1"
    )
    SocialInboxItem.objects.create(
        account=account,
        kind="dm",
        external_id="m-1",
        received_at=timezone.now(),
    )
    with pytest.raises(IntegrityError):
        SocialInboxItem.objects.create(
            account=account,
            kind="dm",
            external_id="m-1",
            received_at=timezone.now(),
        )


@pytest.mark.django_db
def test_dismissed_inbox_item_not_resurrected_on_update_or_create():
    """Mirrors the refresh task's dedup logic — `defaults` deliberately omits status."""
    account = SocialAccount.objects.create(
        platform=Platform.INSTAGRAM_BUSINESS, external_id="ig-1"
    )
    item = SocialInboxItem.objects.create(
        account=account,
        kind="dm",
        external_id="m-1",
        received_at=timezone.now(),
        status=InboxStatus.DISMISSED,
    )
    SocialInboxItem.objects.update_or_create(
        account=account,
        external_id="m-1",
        defaults={
            "kind": "dm",
            "preview": "edited",
            "received_at": timezone.now(),
        },
    )
    item.refresh_from_db()
    assert item.status == InboxStatus.DISMISSED
    assert item.preview == "edited"
