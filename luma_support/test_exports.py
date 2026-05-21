import pytest
from django.test import Client as DjangoClient

from tickets.models import Ticket

pytestmark = pytest.mark.django_db


def test_ticket_list_csv_export(engineer_user, client_record):
    Ticket.objects.create(client=client_record, subject="Alpha", priority="high")
    Ticket.objects.create(client=client_record, subject="Beta", priority="low")

    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.get("/tickets/?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    body = resp.content.decode("utf-8")
    # Header row, two ticket rows.
    lines = [line for line in body.splitlines() if line.strip()]
    assert lines[0].startswith("id,subject,client,system")
    assert any("Alpha" in line for line in lines[1:])
    assert any("Beta" in line for line in lines[1:])


def test_csv_export_respects_filters(engineer_user, client_record):
    Ticket.objects.create(client=client_record, subject="Alpha", priority="high")
    Ticket.objects.create(client=client_record, subject="Beta", priority="low")

    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.get("/tickets/?priority=high&export=csv")
    body = resp.content.decode("utf-8")
    assert "Alpha" in body
    assert "Beta" not in body
