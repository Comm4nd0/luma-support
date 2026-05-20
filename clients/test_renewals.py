"""Tests for the care-plan renewal reminder beat task."""
from datetime import timedelta

import pytest
from django.utils import timezone

from notifications.models import Notification

from .models import CarePlanTier, Client
from .tasks import check_care_plan_renewals


@pytest.mark.django_db
def test_reminder_fires_at_7d(engineer_user):
    Client.objects.create(
        name="A",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=30,
        care_plan_renewal=timezone.localdate() + timedelta(days=7),
    )
    check_care_plan_renewals()
    n = Notification.objects.filter(
        type=Notification.Type.CARE_PLAN_RENEWAL, user=engineer_user
    )
    assert n.count() == 1


@pytest.mark.django_db
def test_reminder_does_not_fire_at_arbitrary_day(engineer_user):
    Client.objects.create(
        name="B",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=30,
        care_plan_renewal=timezone.localdate() + timedelta(days=5),
    )
    check_care_plan_renewals()
    assert (
        Notification.objects.filter(
            type=Notification.Type.CARE_PLAN_RENEWAL
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_reminder_dedupes_within_a_day(engineer_user):
    Client.objects.create(
        name="C",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=30,
        care_plan_renewal=timezone.localdate() + timedelta(days=14),
    )
    check_care_plan_renewals()
    check_care_plan_renewals()
    assert (
        Notification.objects.filter(
            type=Notification.Type.CARE_PLAN_RENEWAL
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_overdue_renewal_alerts(engineer_user):
    Client.objects.create(
        name="D",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
        monthly_fee=70,
        care_plan_renewal=timezone.localdate() - timedelta(days=2),
    )
    check_care_plan_renewals()
    n = Notification.objects.filter(
        type=Notification.Type.CARE_PLAN_RENEWAL, user=engineer_user
    ).first()
    assert n is not None
    assert "overdue" in n.title.lower()


@pytest.mark.django_db
def test_no_alert_for_clients_without_a_plan(engineer_user):
    Client.objects.create(
        name="E",
        care_plan_tier=CarePlanTier.NONE,
        care_plan_renewal=timezone.localdate() + timedelta(days=7),
    )
    check_care_plan_renewals()
    assert (
        Notification.objects.filter(
            type=Notification.Type.CARE_PLAN_RENEWAL
        ).count()
        == 0
    )
