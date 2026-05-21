"""SavedTicketFilter CRUD + portal save/list."""
import pytest
from django.test import Client as DjangoClient
from rest_framework.test import APIClient

from tickets.models import SavedTicketFilter

pytestmark = pytest.mark.django_db


def test_api_user_only_sees_own_filters(engineer_user, admin_user):
    SavedTicketFilter.objects.create(
        user=engineer_user, name="mine", querystring="priority=high"
    )
    SavedTicketFilter.objects.create(
        user=admin_user, name="theirs", querystring="priority=low"
    )
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/tickets/saved-filters/")
    body = resp.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    names = {r["name"] for r in rows}
    assert names == {"mine"}


def test_api_create_owned_by_caller(engineer_user):
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.post(
        "/api/v1/tickets/saved-filters/",
        {"name": "Critical UniFi", "querystring": "priority=critical&tag=unifi",
         "pinned": True},
        format="json",
    )
    assert resp.status_code == 201
    sf = SavedTicketFilter.objects.get()
    assert sf.user == engineer_user
    assert sf.pinned is True


def test_portal_save_view_creates_and_redirects(engineer_user):
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.post(
        "/tickets/saved-filters/save/",
        {"name": "Open + waiting", "querystring": "status=waiting", "pinned": "1"},
    )
    assert resp.status_code == 302
    assert "/tickets/?status=waiting" in resp.url
    assert SavedTicketFilter.objects.filter(
        user=engineer_user, name="Open + waiting"
    ).exists()


def test_portal_save_dedupes_on_name(engineer_user):
    SavedTicketFilter.objects.create(
        user=engineer_user, name="Foo", querystring="status=new"
    )
    web = DjangoClient()
    web.force_login(engineer_user)
    web.post(
        "/tickets/saved-filters/save/",
        {"name": "Foo", "querystring": "status=closed"},
    )
    sf = SavedTicketFilter.objects.get(user=engineer_user, name="Foo")
    assert sf.querystring == "status=closed"


def test_portal_delete_view_removes_filter(engineer_user):
    sf = SavedTicketFilter.objects.create(
        user=engineer_user, name="Foo", querystring="x=y"
    )
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.post(f"/tickets/saved-filters/{sf.pk}/delete/")
    assert resp.status_code == 302
    assert not SavedTicketFilter.objects.filter(pk=sf.pk).exists()
