"""Tests for the onboarding checklist + Lead-conversion seeding."""
import pytest

from leads.models import Lead, LeadStage

from .models import (
    ClientOnboardingTask,
    OnboardingTaskTemplate,
    seed_onboarding_tasks,
)


@pytest.mark.django_db
def test_defaults_seeded_via_migration():
    # The data migration installs the canonical set.
    titles = list(
        OnboardingTaskTemplate.objects.values_list("title", flat=True)
    )
    assert "Send welcome email" in titles
    assert "Issue first invoice" in titles


@pytest.mark.django_db
def test_seed_creates_tasks_for_new_client(client_record):
    n = seed_onboarding_tasks(client_record)
    assert n > 0
    assert (
        ClientOnboardingTask.objects.filter(client=client_record).count() == n
    )


@pytest.mark.django_db
def test_seed_is_idempotent(client_record):
    seed_onboarding_tasks(client_record)
    again = seed_onboarding_tasks(client_record)
    # Second call adds nothing because the titles already exist.
    assert again == 0


@pytest.mark.django_db
def test_lead_conversion_seeds_onboarding(engineer_user):
    lead = Lead.objects.create(
        name="Bayly Co",
        email="b@bayly.test",
        stage=LeadStage.QUALIFIED,
    )
    client = lead.convert_to_client(by_user=engineer_user)
    assert ClientOnboardingTask.objects.filter(client=client).exists()
