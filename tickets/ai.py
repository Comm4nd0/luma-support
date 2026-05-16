"""Claude-powered ticket reply drafts.

`draft_reply(ticket)` returns an engineer-side draft message that
incorporates the ticket subject + description, the public conversation
so far, and the top-3 KB articles suggested by `knowledge.ai`. It
returns "" when ANTHROPIC_API_KEY is empty or the call fails — never
raises — so the calling view can always render a button safely.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def draft_reply(ticket) -> str:
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return ""
    try:
        return _claude_draft(ticket)
    except Exception:
        logger.exception("tickets.ai.draft_reply failed for ticket #%s", ticket.pk)
        return ""


def _claude_draft(ticket) -> str:
    from anthropic import Anthropic

    from knowledge.ai import suggest_articles

    suggestions = suggest_articles(
        ticket.subject, ticket.description or "", limit=3
    )

    notes = ticket.notes.select_related("author").order_by("created_at")
    history_lines = []
    for note in notes:
        if note.internal:
            continue  # don't feed internal notes back into a client-facing draft
        who = "Client" if note.author and getattr(note.author, "is_client", False) else "Engineer"
        history_lines.append(f"{who}: {note.body.strip()}")
    history = "\n\n".join(history_lines) or "(no prior public notes)"

    kb_block = (
        "\n\n".join(
            f"### {s.article.title}\n{s.article.content[:1500]}"
            for s in suggestions
        )
        or "(no relevant KB articles)"
    )

    system_prompt = (
        "You are a UK-based IT support engineer at Luma Tech Solutions. "
        "Draft a polite, concise reply to the client for the ticket below. "
        "Tone: helpful, professional, plain English. Reference KB articles "
        "only when they directly apply. Do not fabricate steps you can't "
        "back up. Keep the reply under 200 words. Do not include a sign-off "
        "or signature — the engineer adds their own."
    )

    user_prompt = (
        f"Client: {ticket.client.name}\n"
        f"Subject: {ticket.subject}\n\n"
        f"Description:\n{ticket.description or '(none)'}\n\n"
        f"Public conversation so far:\n{history}\n\n"
        f"Possibly-relevant KB articles:\n{kb_block}"
    )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=600,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(getattr(b, "text", "") for b in msg.content).strip()
