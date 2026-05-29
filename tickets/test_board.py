"""Ticket board grouping + scoping."""
import pytest
from django.test import Client as DjangoClient

from tickets.models import Ticket, TicketTag

pytestmark = pytest.mark.django_db


def test_board_groups_open_tickets_by_status(engineer_user, client_record):
    new = Ticket.objects.create(client=client_record, subject="new ticket")
    Ticket.objects.filter(pk=new.pk).update(status=Ticket.Status.NEW)
    closed = Ticket.objects.create(client=client_record, subject="closed ticket")
    Ticket.objects.filter(pk=closed.pk).update(status=Ticket.Status.CLOSED)
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.get("/tickets/board/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Open ticket shows up.
    assert "new ticket" in body
    # Closed ticket is excluded from the board.
    assert "closed ticket" not in body


def test_board_filters_by_tag(engineer_user, client_record):
    a = Ticket.objects.create(client=client_record, subject="alpha")
    Ticket.objects.create(client=client_record, subject="beta")
    tag = TicketTag.objects.create(name="UniFi", slug="unifi")
    a.tags.add(tag)
    web = DjangoClient()
    web.force_login(engineer_user)
    resp = web.get("/tickets/board/?tag=unifi")
    body = resp.content.decode()
    assert "alpha" in body
    assert "beta" not in body
