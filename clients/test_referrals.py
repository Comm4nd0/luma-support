from decimal import Decimal

import pytest
from django.urls import reverse

from billing.services import generate_contract_invoice
from leads.models import Lead, LeadSource
from notifications.models import Notification

from .models import CarePlanTier, Client, ReferralCode
from .referrals import (
    credit_referrer,
)

# -----------------------------------------------------------------
# ReferralCode model
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_code_generates_lazily(client_record):
    code = ReferralCode.for_client(client_record)
    assert code.code.startswith("LUMA-")
    # Idempotent — second call returns the same row.
    again = ReferralCode.for_client(client_record)
    assert again.pk == code.pk


# -----------------------------------------------------------------
# credit_referrer
# -----------------------------------------------------------------


@pytest.fixture
def referrer(db):
    return Client.objects.create(
        name="Referrer Bob",
        email="bob@example.com",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=Decimal("30.00"),
    )


@pytest.mark.django_db
def test_credit_added_on_conversion(referrer, engineer_user, settings):
    settings.REFERRAL_CREDIT_GBP = Decimal("25.00")
    lead = Lead.objects.create(
        name="Friend of Bob",
        referring_client=referrer,
        source=LeadSource.REFERRAL,
    )
    lead.convert_to_client(by_user=engineer_user)
    code = ReferralCode.objects.get(client=referrer)
    assert code.credit_balance == Decimal("25.00")
    assert code.lifetime_credit == Decimal("25.00")
    assert Notification.objects.filter(
        type=Notification.Type.REFERRAL_CREDIT
    ).exists()


@pytest.mark.django_db
def test_credit_is_idempotent_per_lead(referrer, settings):
    settings.REFERRAL_CREDIT_GBP = Decimal("25.00")
    lead = Lead.objects.create(
        name="Once",
        referring_client=referrer,
    )
    credit_referrer(lead)
    credit_referrer(lead)
    code = ReferralCode.objects.get(client=referrer)
    assert code.credit_balance == Decimal("25.00")


@pytest.mark.django_db
def test_apply_credit_caps_at_subtotal(referrer, settings):
    """A £100 balance against a £30 invoice only consumes £30."""
    settings.REFERRAL_CREDIT_GBP = Decimal("25.00")
    code = ReferralCode.for_client(referrer)
    code.credit_balance = Decimal("100.00")
    code.lifetime_credit = Decimal("100.00")
    code.save()

    from datetime import date

    inv, was_new = generate_contract_invoice(referrer, date(2026, 5, 1))
    assert was_new
    inv.refresh_from_db()
    code.refresh_from_db()

    # Net invoice = monthly_fee - applied credit = 30 - 30 = 0.
    assert inv.total == Decimal("0.00")
    # Remaining balance after applying £30 of the £100 available.
    assert code.credit_balance == Decimal("70.00")
    # Negative line is the credit row.
    assert inv.lines.filter(unit_amount__lt=0).count() == 1


@pytest.mark.django_db
def test_apply_credit_with_zero_balance_is_a_noop(client_record):
    from datetime import date

    client_record.care_plan_tier = CarePlanTier.PROFESSIONAL
    client_record.monthly_fee = Decimal("50.00")
    client_record.save()
    inv, was_new = generate_contract_invoice(client_record, date(2026, 5, 1))
    assert was_new
    assert inv.total == Decimal("50.00")
    # No credit row created.
    assert inv.lines.filter(unit_amount__lt=0).count() == 0


# -----------------------------------------------------------------
# Public /r/<code>/ and contact-form attribution
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_referral_redirect_to_contact(client, referrer):
    code = ReferralCode.for_client(referrer)
    resp = client.get(f"/r/{code.code}/")
    assert resp.status_code == 302
    assert resp.url == f"/contact/?ref={code.code}"


@pytest.mark.django_db
def test_contact_form_resolves_ref_to_client(client, referrer):
    from django.core.cache import cache

    cache.clear()
    code = ReferralCode.for_client(referrer)
    resp = client.post(
        f"/contact/?ref={code.code}",
        data={
            "name": "New Prospect",
            "email": "np@example.com",
            "message": "Bob sent me.",
            "website": "",
        },
    )
    assert resp.status_code == 200
    lead = Lead.objects.get(name="New Prospect")
    assert lead.source == LeadSource.REFERRAL
    assert lead.referring_client_id == referrer.pk


@pytest.mark.django_db
def test_unknown_ref_code_still_captures_lead(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/?ref=BOGUS-CODE",
        data={
            "name": "Stranger Bob",
            "email": "sb@example.com",
            "message": "Hi.",
            "website": "",
        },
    )
    assert resp.status_code == 200
    lead = Lead.objects.get(name="Stranger Bob")
    assert lead.source == LeadSource.REFERRAL
    assert lead.referring_client_id is None
    assert "BOGUS-CODE" in lead.source_detail


# -----------------------------------------------------------------
# Client-facing /refer/ dashboard
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_refer_dashboard_for_client_user(client, referrer):
    from accounts.models import User

    cu = User.objects.create_user(
        email="bobby@example.com",
        password="x",
        role=User.Role.CLIENT,
        client=referrer,
    )
    client.force_login(cu)
    resp = client.get(reverse("portal:refer"))
    assert resp.status_code == 200
    assert b"LUMA-" in resp.content
    assert b"/r/" in resp.content
