"""Parse inbound emails into Tickets and TicketNotes.

The IMAP poll loop lives in `tickets.tasks.poll_inbound_mail`. This
module is the pure-Python part: a raw RFC-822 byte stream goes in, an
`InboundResult` comes out describing what (if anything) was created.

Threading is by plus-addressing: the outbound email sets a Reply-To of
`support+<ticket_id>@<domain>`, so when a client replies their mail
client populates the To: with that address. We extract the ticket id
from the To/Cc list. If we can't find a plus-addressed ticket id, we
fall back to treating it as a new ticket from a known sender.
"""
from __future__ import annotations

import email
import logging
import re
from dataclasses import dataclass
from email.message import Message
from email.policy import default as default_policy
from email.utils import getaddresses
from typing import Iterable, Optional

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from .models import Attachment, Ticket, TicketNote

logger = logging.getLogger(__name__)

# "support+42@example.com" → 42
_PLUS_ADDRESS_RE = re.compile(r"\+(\d+)@", re.I)
# "On Thu, 1 May 2026 at 09:14, Marco wrote:" — strip everything from here.
_QUOTED_REPLY_RE = re.compile(r"^On\s.+wrote:\s*$", re.M)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class InboundResult:
    ticket: Optional[Ticket]
    note: Optional[TicketNote]
    created_new_ticket: bool


def parse_message(raw_bytes: bytes) -> Message:
    return email.message_from_bytes(raw_bytes, policy=default_policy)


def _addr_list(msg: Message, header: str) -> list[str]:
    raw = msg.get_all(header, [])
    return [a for _, a in getaddresses(raw) if a]


def extract_ticket_id(addrs: Iterable[str]) -> Optional[int]:
    for addr in addrs:
        m = _PLUS_ADDRESS_RE.search(addr or "")
        if m:
            return int(m.group(1))
    return None


def extract_body(msg: Message) -> str:
    """Best-effort plain-text body with the simplest quoted reply removed."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_attachment():
                continue
            if part.get_content_type() == "text/plain":
                body = part.get_content()
                break
        if not body:
            for part in msg.walk():
                if part.is_attachment():
                    continue
                if part.get_content_type() == "text/html":
                    body = _HTML_TAG_RE.sub("", part.get_content())
                    break
    elif msg.get_content_type() == "text/plain":
        body = msg.get_content()
    elif msg.get_content_type() == "text/html":
        body = _HTML_TAG_RE.sub("", msg.get_content())

    m = _QUOTED_REPLY_RE.search(body)
    if m:
        body = body[: m.start()].rstrip()
    return body.strip()


def extract_attachments(msg: Message):
    """Yield (filename, bytes) for every part flagged as an attachment."""
    for part in msg.walk():
        if not part.is_attachment():
            continue
        filename = part.get_filename() or "attachment.bin"
        payload = part.get_payload(decode=True)
        if payload:
            yield filename, payload


def _find_user_by_email(addr: str):
    User = get_user_model()
    return User.objects.filter(email__iexact=addr, is_active=True).first()


def ingest(raw_bytes: bytes) -> InboundResult:
    """Turn one RFC-822 message into a Ticket or TicketNote.

    Behavior:
      - Plus-addressed To: → TicketNote(internal=False) on that ticket.
      - Otherwise sender known → new Ticket on that user's client.
      - Otherwise dropped (logged) — caller is expected to leave the
        message Seen so we don't loop on it.
    """
    msg = parse_message(raw_bytes)
    subject = (msg.get("Subject") or "(no subject)").strip() or "(no subject)"
    from_addrs = _addr_list(msg, "From")
    from_addr = from_addrs[0] if from_addrs else ""
    to_addrs = _addr_list(msg, "To") + _addr_list(msg, "Cc")

    body = extract_body(msg)
    attachments = list(extract_attachments(msg))

    ticket_id = extract_ticket_id(to_addrs)
    user = _find_user_by_email(from_addr) if from_addr else None

    if ticket_id is not None:
        try:
            ticket = Ticket.objects.get(pk=ticket_id)
        except Ticket.DoesNotExist:
            logger.warning("Inbound reply to unknown ticket #%s", ticket_id)
            return InboundResult(None, None, False)
        note = TicketNote.objects.create(
            ticket=ticket,
            author=user,
            body=body or f"(Reply from {from_addr})",
            internal=False,
        )
        _save_attachments(ticket, user, attachments)
        return InboundResult(ticket=ticket, note=note, created_new_ticket=False)

    if user is None:
        logger.info("Inbound from unknown sender %r — dropping", from_addr)
        return InboundResult(None, None, False)

    client = user.client
    if client is None:
        logger.info("Inbound from %s has no client link — dropping", from_addr)
        return InboundResult(None, None, False)

    ticket = Ticket.objects.create(
        client=client,
        subject=subject[:300],
        description=body,
        created_by=user,
    )
    _save_attachments(ticket, user, attachments)
    return InboundResult(ticket=ticket, note=None, created_new_ticket=True)


def _save_attachments(ticket: Ticket, user, attachments) -> None:
    for filename, payload in attachments:
        a = Attachment(ticket=ticket, uploaded_by=user, filename=filename)
        a.file.save(filename, ContentFile(payload), save=True)
