"""Web portal site-visit logbook (parity with the mobile screen)."""
import pytest
from django.test import Client as DjangoClient
from django.urls import reverse

from clients.models import SiteVisit

pytestmark = pytest.mark.django_db


def _client_user(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email="cu@acme.test", password="x",
        role=User.Role.CLIENT, client=client_record,
    )


def test_page_renders_for_staff(engineer_user, client_record):
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.get(reverse("portal:site_visit_list"))
    assert resp.status_code == 200
    assert b"Site visits" in resp.content
    assert client_record.name.encode() in resp.content  # in the start dropdown


def test_client_user_is_redirected(client_record):
    web = DjangoClient()
    web.force_login(_client_user(client_record))
    resp = web.get(reverse("portal:site_visit_list"))
    # StaffRequiredMixin bounces non-staff to the dashboard.
    assert resp.status_code == 302
    assert reverse("portal:dashboard") in resp["Location"]


def test_staff_can_start_visit(engineer_user, client_record):
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.post(
        reverse("portal:site_visit_list"),
        {"action": "start", "client": client_record.pk},
    )
    assert resp.status_code == 302
    visit = SiteVisit.objects.get()
    assert visit.client == client_record
    assert visit.user == engineer_user
    assert visit.is_open


def test_staff_can_end_visit_and_bill_ticket(engineer_user, client_record):
    from datetime import timedelta

    from django.utils import timezone

    from tickets.models import Ticket

    visit = SiteVisit.objects.create(client=client_record, user=engineer_user)
    SiteVisit.objects.filter(pk=visit.pk).update(
        started_at=timezone.now() - timedelta(minutes=30)
    )
    ticket = Ticket.objects.create(client=client_record, subject="x")

    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.post(
        reverse("portal:site_visit_list"),
        {"action": "end", "visit": visit.pk, "ticket": ticket.pk,
         "notes": "fixed the AP"},
    )
    assert resp.status_code == 302
    visit.refresh_from_db()
    assert visit.ended_at is not None
    assert "fixed the AP" in visit.notes
    assert visit.time_entry is not None
    assert visit.time_entry.ticket == ticket


def test_cannot_end_other_engineers_visit(engineer_user, client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    other = User.objects.create_user(
        email="eng-other@acme.test", password="x", role=User.Role.ENGINEER,
    )
    visit = SiteVisit.objects.create(client=client_record, user=other)

    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.post(
        reverse("portal:site_visit_list"),
        {"action": "end", "visit": visit.pk},
    )
    assert resp.status_code == 302
    visit.refresh_from_db()
    assert visit.ended_at is None  # not closed — wasn't their visit
