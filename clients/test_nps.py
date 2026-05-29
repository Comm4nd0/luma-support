"""Tests for the quarterly NPS survey + Promoter → referral nudge."""
import pytest
from django.core import mail

from .models import CarePlanTier, Client, Contact, NpsResponse
from .tasks import send_nps_survey


@pytest.fixture
def nps_client(db):
    c = Client.objects.create(
        name="NPS Co",
        email="ops@nps.co",
        care_plan_tier=CarePlanTier.ESSENTIAL,
        monthly_fee=30,
    )
    Contact.objects.create(
        client=c, name="Pat Lead", email="pat@nps.co", is_primary=True
    )
    return c


@pytest.mark.django_db
def test_send_nps_survey_creates_one_response_per_quarter(nps_client):
    send_nps_survey()
    send_nps_survey()  # second call is a no-op via the unique constraint
    assert NpsResponse.objects.filter(client=nps_client).count() == 1
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["pat@nps.co"]


@pytest.mark.django_db
def test_nps_skips_clients_without_a_plan(db):
    Client.objects.create(name="No plan", care_plan_tier=CarePlanTier.NONE)
    send_nps_survey()
    assert NpsResponse.objects.count() == 0


@pytest.mark.django_db
def test_promoter_thanks_page_shows_referral_link(client, nps_client):
    send_nps_survey()
    resp = NpsResponse.objects.get(client=nps_client)

    page = client.post(f"/nps/{resp.token}/", data={"score": "10"})
    assert page.status_code == 200
    resp.refresh_from_db()
    assert resp.score == 10
    assert resp.category == "promoter"
    # Promoter thanks page surfaces the referral link.
    assert b"/r/" in page.content


@pytest.mark.django_db
def test_detractor_does_not_show_referral_link(client, nps_client):
    send_nps_survey()
    resp = NpsResponse.objects.get(client=nps_client)
    page = client.post(f"/nps/{resp.token}/", data={"score": "3"})
    assert page.status_code == 200
    resp.refresh_from_db()
    assert resp.category == "detractor"
    assert b"/r/" not in page.content


@pytest.mark.django_db
def test_invalid_token_is_404(client):
    resp = client.get("/nps/not-a-real-token/")
    assert resp.status_code == 404
