import os

# Force tests onto SQLite + an in-process Celery so we don't need
# Postgres / Redis to run the suite.
os.environ.setdefault("POSTGRES_HOST", "")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")

import pytest  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402


def pytest_configure(config):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False
    settings.CELERY_TASK_STORE_EAGER_RESULT = False
    settings.CELERY_BROKER_URL = "memory://"
    settings.CELERY_RESULT_BACKEND = "cache+memory://"


from clients.models import CarePlanTier, Client  # noqa: E402


@pytest.fixture
def admin_user(db):
    User = get_user_model()
    user = User.objects.create_user(
        email="admin@example.com", password="password123", role="admin",
        is_staff=True, is_superuser=True,
    )
    return user


@pytest.fixture
def engineer_user(db):
    User = get_user_model()
    return User.objects.create_user(
        email="engineer@example.com", password="password123", role="engineer",
    )


@pytest.fixture
def client_record(db):
    return Client.objects.create(
        name="Test Client",
        company="Test Co",
        email="contact@test.example.com",
        care_plan_tier=CarePlanTier.PROFESSIONAL,
    )
