"""CSAT survey: signal trigger on CLOSED, email task, public submission view."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core import mail
from django.test import Client as DjangoClient
from django.urls import reverse

from notifications.tasks import send_csat_email
from tickets.models import CsatResponse, Ticket

pytestmark = pytest.mark.django_db


def _create_client_user(email="alice@acme.test", client=None):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email=email,
        password="x",
        role=User.Role.CLIENT,
        client=client,
    )


# ----- signal -----------------------------------------------------------


def test_closing_a_ticket_triggers_csat_email(client_record):
    user = _create_client_user(client=client_record)
    ticket = Ticket.objects.create(
        client=client_record, subject="VPN drop", created_by=user
    )
    with patch("notifications.tasks.send_csat_email.delay") as send:
        ticket.status = Ticket.Status.CLOSED
        ticket.save()
    send.assert_called_once_with(ticket.pk)


def test_non_close_transition_does_not_trigger_csat(client_record):
    user = _create_client_user(client=client_record)
    ticket = Ticket.objects.create(
        client=client_record, subject="VPN drop", created_by=user
    )
    with patch("notifications.tasks.send_csat_email.delay") as send:
        ticket.status = Ticket.Status.RESOLVED
        ticket.save()
    send.assert_not_called()


# ----- email task -------------------------------------------------------


def test_send_csat_email_creates_pending_response_and_sends(client_record, settings):
    settings.SITE_URL = "https://support.example.com"
    user = _create_client_user(client=client_record)
    ticket = Ticket.objects.create(client=client_record, subject="hi", created_by=user)
    mail.outbox.clear()  # drop the "ticket created" email

    result = send_csat_email(ticket.pk)

    assert result == "sent"
    csat = CsatResponse.objects.get(ticket=ticket)
    assert csat.rating is None  # pending
    assert csat.token
    assert len(mail.outbox) == 1
    assert csat.token in mail.outbox[0].body
    assert "alice@acme.test" in mail.outbox[0].to


def test_send_csat_email_is_idempotent(client_record):
    user = _create_client_user(client=client_record)
    ticket = Ticket.objects.create(client=client_record, subject="hi", created_by=user)
    mail.outbox.clear()

    send_csat_email(ticket.pk)
    second = send_csat_email(ticket.pk)
    assert second == "already-sent"
    assert CsatResponse.objects.filter(ticket=ticket).count() == 1
    assert len(mail.outbox) == 1


def test_send_csat_email_skips_without_recipient(client_record):
    # No email on the client, no created_by → no recipient.
    client_record.email = ""
    client_record.save(update_fields=["email"])
    ticket = Ticket.objects.create(client=client_record, subject="anon")
    mail.outbox.clear()

    result = send_csat_email(ticket.pk)
    assert result == "no-recipient"
    assert len(mail.outbox) == 0


def test_send_csat_email_falls_back_to_client_email(client_record):
    # No created_by — use client's listed email.
    ticket = Ticket.objects.create(client=client_record, subject="anon")
    mail.outbox.clear()

    send_csat_email(ticket.pk)
    assert mail.outbox[0].to == [client_record.email]


# ----- public submission view ------------------------------------------


def _csat_url(token):
    return reverse("portal:csat_submit", args=[token])


def test_submission_form_renders_for_pending_csat(client_record):
    user = _create_client_user(client=client_record)
    t = Ticket.objects.create(client=client_record, subject="x", created_by=user)
    csat = CsatResponse.objects.create(ticket=t)
    resp = DjangoClient().get(_csat_url(csat.token))
    assert resp.status_code == 200
    assert b"How did we do" in resp.content


def test_submission_post_records_rating(client_record):
    user = _create_client_user(client=client_record)
    t = Ticket.objects.create(client=client_record, subject="x", created_by=user)
    csat = CsatResponse.objects.create(ticket=t)
    resp = DjangoClient().post(
        _csat_url(csat.token), {"rating": "4", "comment": "good"}
    )
    assert resp.status_code == 200
    csat.refresh_from_db()
    assert csat.rating == 4
    assert csat.comment == "good"
    assert csat.responded_at is not None


def test_submission_rejects_out_of_range_rating(client_record):
    user = _create_client_user(client=client_record)
    t = Ticket.objects.create(client=client_record, subject="x", created_by=user)
    csat = CsatResponse.objects.create(ticket=t)
    resp = DjangoClient().post(_csat_url(csat.token), {"rating": "7"})
    assert resp.status_code == 200  # re-renders form
    csat.refresh_from_db()
    assert csat.rating is None


def test_submission_is_single_use(client_record):
    user = _create_client_user(client=client_record)
    t = Ticket.objects.create(client=client_record, subject="x", created_by=user)
    csat = CsatResponse.objects.create(ticket=t, rating=5)
    resp = DjangoClient().post(_csat_url(csat.token), {"rating": "1"})
    assert resp.status_code == 200
    csat.refresh_from_db()
    assert csat.rating == 5  # unchanged


def test_unknown_token_404s():
    resp = DjangoClient().get(_csat_url("nope"))
    assert resp.status_code == 404
