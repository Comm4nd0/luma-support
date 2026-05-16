"""Tests for tickets.inbound — RFC-822 → Ticket / TicketNote."""
from email.message import EmailMessage

import pytest
from django.contrib.auth import get_user_model

from clients.models import CarePlanTier, Client
from tickets.inbound import (
    InboundResult,
    extract_body,
    extract_ticket_id,
    ingest,
    parse_message,
)
from tickets.models import Ticket, TicketNote

pytestmark = pytest.mark.django_db


@pytest.fixture
def acme(db):
    return Client.objects.create(name="Acme", care_plan_tier=CarePlanTier.PROFESSIONAL)


@pytest.fixture
def alice(db, acme):
    User = get_user_model()
    return User.objects.create_user(
        email="alice@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=acme,
    )


def _eml(to, from_, subject, body, attachments=None, content_type=None):
    msg = EmailMessage()
    msg["To"] = to
    msg["From"] = from_
    msg["Subject"] = subject
    if content_type == "html":
        msg.set_content(body, subtype="html")
    else:
        msg.set_content(body)
    if attachments:
        for filename, payload in attachments:
            msg.add_attachment(
                payload,
                maintype="application",
                subtype="octet-stream",
                filename=filename,
            )
    return msg.as_bytes()


def test_extract_ticket_id_picks_first_plus_addr():
    assert extract_ticket_id(["support+42@example.com"]) == 42
    assert extract_ticket_id(["foo@bar", "support+7@example.com"]) == 7
    assert extract_ticket_id(["foo@bar"]) is None
    assert extract_ticket_id([]) is None


def test_new_ticket_from_known_sender(alice):
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "alice@acme.test",
        "WiFi is down",
        "It went down at 9am.",
    )
    result: InboundResult = ingest(raw)
    assert result.created_new_ticket is True
    assert result.ticket.subject == "WiFi is down"
    assert result.ticket.client == alice.client
    assert result.ticket.created_by == alice
    assert "9am" in result.ticket.description


def test_reply_via_plus_addressing_creates_note(alice):
    ticket = Ticket.objects.create(client=alice.client, subject="Original issue")
    raw = _eml(
        f"support+{ticket.pk}@lumatechsolutions.co.uk",
        "alice@acme.test",
        f"Re: {ticket.subject}",
        "Still broken — tried rebooting.",
    )
    result = ingest(raw)
    assert result.created_new_ticket is False
    assert result.ticket.pk == ticket.pk
    assert result.note is not None
    assert "Still broken" in result.note.body
    assert result.note.internal is False
    assert result.note.author == alice
    # No new ticket created.
    assert Ticket.objects.count() == 1


def test_reply_to_missing_ticket_is_dropped(alice):
    raw = _eml(
        "support+9999@lumatechsolutions.co.uk",
        "alice@acme.test",
        "Re: nope",
        "Hello?",
    )
    result = ingest(raw)
    assert result.ticket is None
    assert TicketNote.objects.count() == 0


def test_unknown_sender_dropped(db):
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "stranger@elsewhere.test",
        "hello",
        "is this thing on?",
    )
    result = ingest(raw)
    assert result.ticket is None
    assert Ticket.objects.count() == 0


def test_client_user_with_no_client_link_dropped(db):
    User = get_user_model()
    User.objects.create_user(email="orphan@acme.test", password="x", role=User.Role.CLIENT)
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "orphan@acme.test",
        "hi",
        "no client link",
    )
    result = ingest(raw)
    assert result.ticket is None


def test_quoted_reply_stripped(alice):
    body = (
        "I tried that, still no luck.\n"
        "\n"
        "On Thu, 1 May 2026 at 09:14, Marco wrote:\n"
        "> Have you tried rebooting?\n"
    )
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "alice@acme.test",
        "Re: still broken",
        body,
    )
    result = ingest(raw)
    assert result.ticket is not None
    assert "rebooting" not in result.ticket.description.lower()
    assert result.ticket.description.startswith("I tried that")


def test_html_only_body_stripped(alice):
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "alice@acme.test",
        "html test",
        "<p>Hello <strong>world</strong></p>",
        content_type="html",
    )
    result = ingest(raw)
    assert result.ticket is not None
    assert "<p>" not in result.ticket.description
    assert "Hello" in result.ticket.description


def test_attachment_saved(alice, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    raw = _eml(
        "support@lumatechsolutions.co.uk",
        "alice@acme.test",
        "with photo",
        "see attached",
        attachments=[("photo.jpg", b"\xff\xd8\xff\xe0fakejpg")],
    )
    result = ingest(raw)
    assert result.ticket.attachments.count() == 1
    a = result.ticket.attachments.first()
    assert a.filename == "photo.jpg"
    assert a.uploaded_by == alice


def test_parse_message_handles_bare_bytes():
    raw = b"Subject: hi\r\nFrom: x@y\r\nTo: z@w\r\n\r\nbody"
    msg = parse_message(raw)
    assert msg["Subject"] == "hi"
    assert extract_body(msg) == "body"
