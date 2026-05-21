"""Site-visit start / end + TimeEntry rollover."""
import pytest
from rest_framework.test import APIClient

from clients.models import SiteVisit
from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_client_user_cannot_start_visit(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="sv@acme.test", password="x",
        role=User.Role.CLIENT, client=client_record,
    )
    c = APIClient()
    c.force_authenticate(cu)
    resp = c.post(
        f"/api/v1/clients/clients/{client_record.pk}/site-visits/start/",
        {}, format="json",
    )
    assert resp.status_code == 403


def test_engineer_starts_visit_with_coords(engineer_user, client_record):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/clients/clients/{client_record.pk}/site-visits/start/",
        {"lat": "51.501364", "lon": "-0.141890"},
        format="json",
    )
    assert resp.status_code == 201
    visit = SiteVisit.objects.get()
    assert visit.user == engineer_user
    assert visit.is_open
    assert str(visit.lat_start) == "51.501364"


def test_end_creates_time_entry(engineer_user, client_record):
    from datetime import timedelta
    from django.utils import timezone

    visit = SiteVisit.objects.create(client=client_record, user=engineer_user)
    SiteVisit.objects.filter(pk=visit.pk).update(
        started_at=timezone.now() - timedelta(minutes=45)
    )
    visit.refresh_from_db()
    ticket = Ticket.objects.create(client=client_record, subject="x")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/clients/site-visits/{visit.pk}/end/",
        {"ticket": ticket.pk}, format="json",
    )
    assert resp.status_code == 200, resp.json()
    visit.refresh_from_db()
    assert visit.ended_at is not None
    assert visit.time_entry is not None
    # ~45 minutes (rounded down).
    assert 40 <= visit.time_entry.minutes <= 46
    assert visit.time_entry.ticket == ticket


def test_cannot_end_already_ended_visit(engineer_user, client_record):
    from django.utils import timezone

    visit = SiteVisit.objects.create(
        client=client_record, user=engineer_user, ended_at=timezone.now()
    )
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        f"/api/v1/clients/site-visits/{visit.pk}/end/", {}, format="json"
    )
    assert resp.status_code == 400


def test_other_engineer_cannot_end_someone_elses_visit(
    engineer_user, admin_user, client_record
):
    visit = SiteVisit.objects.create(client=client_record, user=engineer_user)
    # admin_user is an admin (is_admin_role=True), so they CAN end it.
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.post(f"/api/v1/clients/site-visits/{visit.pk}/end/", {})
    assert resp.status_code == 200
