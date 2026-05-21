"""Tests for the Stripe Customer Portal session endpoint."""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_portal_returns_url_when_stripe_configured(admin_user, client_record, settings):
    settings.STRIPE_API_KEY = "sk_test_x"
    c = APIClient()
    c.force_authenticate(admin_user)
    with patch(
        "billing.stripe_client.create_customer_portal_session",
        return_value="https://billing.stripe.com/session/abc",
    ):
        resp = c.post(
            "/api/v1/billing/portal-session/",
            {
                "client": client_record.pk,
                "return_url": "https://app.example.com/x",
            },
            format="json",
        )
    assert resp.status_code == 200
    assert resp.json() == {"url": "https://billing.stripe.com/session/abc"}


def test_portal_returns_null_when_stripe_not_configured(
    admin_user, client_record, settings
):
    settings.STRIPE_API_KEY = ""
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.post(
        "/api/v1/billing/portal-session/",
        {"client": client_record.pk, "return_url": "https://x.test/"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json() == {"url": None}


def test_client_user_can_only_open_own_portal(client_record, settings):
    """A logged-in client user can only ask for their own client's portal."""
    from django.contrib.auth import get_user_model

    from clients.models import Client

    settings.STRIPE_API_KEY = "sk_test_x"
    User = get_user_model()
    cu = User.objects.create_user(
        email="cu@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client_record,
    )
    other = Client.objects.create(name="Other co")

    c = APIClient()
    c.force_authenticate(cu)
    # Own client: allowed (just verify routing, mock the stripe call).
    with patch(
        "billing.stripe_client.create_customer_portal_session",
        return_value="https://billing.stripe.com/session/x",
    ):
        ok = c.post(
            "/api/v1/billing/portal-session/",
            {"client": client_record.pk, "return_url": "https://x.test/"},
            format="json",
        )
    assert ok.status_code == 200
    # Different client: 403.
    forbidden = c.post(
        "/api/v1/billing/portal-session/",
        {"client": other.pk, "return_url": "https://x.test/"},
        format="json",
    )
    assert forbidden.status_code == 403
