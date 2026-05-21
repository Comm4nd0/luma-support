import pytest

from features import is_enabled
from features.models import FeatureFlag


@pytest.mark.django_db
def test_missing_flag_returns_false():
    assert is_enabled("does_not_exist") is False


@pytest.mark.django_db
def test_disabled_flag_returns_false():
    FeatureFlag.objects.create(name="ai_triage", enabled=False)
    assert is_enabled("ai_triage") is False


@pytest.mark.django_db
def test_enabled_full_rollout(admin_user):
    FeatureFlag.objects.create(name="ai_triage", enabled=True, percentage=100)
    assert is_enabled("ai_triage", user=admin_user) is True
    # Anonymous case still True at 100%.
    assert is_enabled("ai_triage", user=None) is True


@pytest.mark.django_db
def test_percentage_is_deterministic_per_user(admin_user):
    FeatureFlag.objects.create(name="x", enabled=True, percentage=50)
    first = is_enabled("x", user=admin_user)
    second = is_enabled("x", user=admin_user)
    assert first == second


@pytest.mark.django_db
def test_allowed_users_overrides_percentage(admin_user, engineer_user):
    flag = FeatureFlag.objects.create(name="pilot", enabled=True, percentage=0)
    flag.allowed_users.add(admin_user)
    assert is_enabled("pilot", user=admin_user) is True
    assert is_enabled("pilot", user=engineer_user) is False
