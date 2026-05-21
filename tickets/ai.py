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


def summarise_thread(ticket) -> str:
    """Return a short bullet-point TL;DR of the ticket conversation.

    Returns "" when ANTHROPIC_API_KEY is unset or the call fails so the
    UI can render the button safely; never raises.
    """
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return ""
    try:
        return _claude_summarise(ticket)
    except Exception:
        logger.exception(
            "tickets.ai.summarise_thread failed for ticket #%s", ticket.pk
        )
        return ""


def propose_inbox_actions(tickets) -> list[dict]:
    """For each ticket in ``tickets``, ask Claude what to do next.

    Returns a list of ``{ticket_id, action, reason}`` dicts. Action is
    one of: ``close``, ``reply``, ``ask``, ``defer``. Empty list when
    ANTHROPIC_API_KEY is unset or the call fails — caller can hide the
    feature gracefully.

    Designed for "clear my queue" workflows: present the list as a
    swipe-style approval flow on mobile or a stacked card view on web.
    """
    tickets = list(tickets)
    if not tickets:
        return []
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return []
    try:
        return _claude_inbox_zero(tickets)
    except Exception:
        logger.exception("tickets.ai.propose_inbox_actions failed")
        return []


def _claude_inbox_zero(tickets) -> list[dict]:
    import json

    from anthropic import Anthropic

    lines = []
    for t in tickets:
        last_note = t.notes.order_by("-created_at").first()
        last = (last_note.body[:200] + "…") if last_note and len(last_note.body) > 200 else (last_note.body if last_note else "")
        lines.append(
            f"- id={t.pk} priority={t.priority} status={t.status} "
            f"subject={t.subject!r} last_note={last!r}"
        )
    listing = "\n".join(lines)

    system_prompt = (
        "You triage a small support queue for a UK MSP. For each ticket "
        "below pick exactly one action: 'close' (resolution looks complete), "
        "'reply' (engineer should send a substantive update now), 'ask' "
        "(need more info from the client), or 'defer' (legitimate but "
        "not urgent — push to tomorrow). Respond with strict JSON only: "
        "{\"actions\": [{\"ticket_id\": int, \"action\": str, "
        "\"reason\": str (one short sentence)}, …]}. No prose."
    )
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1200,
        system=system_prompt,
        messages=[{"role": "user", "content": listing}],
    )
    raw = "".join(getattr(b, "text", "") for b in msg.content).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("inbox-zero: claude returned non-JSON: %r", raw[:200])
        return []
    valid = {"close", "reply", "ask", "defer"}
    ids = {t.pk for t in tickets}
    out = []
    for row in data.get("actions") or []:
        try:
            tid = int(row.get("ticket_id"))
        except (TypeError, ValueError):
            continue
        action = row.get("action")
        if tid not in ids or action not in valid:
            continue
        out.append(
            {
                "ticket_id": tid,
                "action": action,
                "reason": (row.get("reason") or "")[:240],
            }
        )
    return out


def draft_kb_article(ticket) -> dict | None:
    """Turn a (typically resolved) ticket into a draft KB article.

    Returns ``{"title": str, "content": str}`` (markdown body) so the
    caller can show the draft for review before publishing. Returns
    ``None`` when ANTHROPIC_API_KEY is unset or the call fails so the
    UI can hide the button.
    """
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return None
    try:
        return _claude_kb_draft(ticket)
    except Exception:
        logger.exception("tickets.ai.draft_kb_article failed for #%s", ticket.pk)
        return None


def _claude_kb_draft(ticket) -> dict | None:
    import json

    from anthropic import Anthropic

    notes = ticket.notes.select_related("author").order_by("created_at")
    history_lines = []
    for note in notes:
        who = (
            "Client"
            if note.author and getattr(note.author, "is_client", False)
            else "Engineer"
        )
        tag = " (internal)" if note.internal else ""
        history_lines.append(f"{who}{tag}: {note.body.strip()}")
    history = "\n\n".join(history_lines) or "(no notes)"

    system_prompt = (
        "You turn a resolved IT support ticket into a draft knowledge-base "
        "article for future readers (other engineers and, optionally, the "
        "client). Lift only the steps and facts — strip names, dates, and "
        "the back-and-forth. Output strict JSON with keys: title (string, "
        "<= 90 chars, action-oriented, no leading 'How to') and content "
        "(markdown body, max ~500 words, use ## headings and numbered "
        "steps where they help). No prose outside the JSON object."
    )
    user_prompt = (
        f"Subject: {ticket.subject}\n\n"
        f"Description:\n{ticket.description or '(none)'}\n\n"
        f"Conversation + internal notes:\n{history}"
    )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = "".join(getattr(b, "text", "") for b in msg.content).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("kb-draft: claude returned non-JSON: %r", raw[:200])
        return None
    title = (data.get("title") or "").strip()[:300]
    content = (data.get("content") or "").strip()
    if not title or not content:
        return None
    return {"title": title, "content": content}


def triage_ticket(ticket) -> dict | None:
    """Return Claude's triage suggestion for a freshly-opened ticket.

    Result shape::

        {"priority": "high", "tag_slugs": ["unifi", "outage"], "reasoning": "..."}

    Returns ``None`` when ANTHROPIC_API_KEY is unset or the call fails
    so callers can no-op safely. Tag slugs are restricted to the set
    of TicketTag rows already in the database — Claude can only pick
    from existing taxonomy, not invent new tags.
    """
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        return None
    try:
        return _claude_triage(ticket)
    except Exception:
        logger.exception("tickets.ai.triage_ticket failed for #%s", ticket.pk)
        return None


def _claude_triage(ticket) -> dict | None:
    import json

    from anthropic import Anthropic

    from .models import TicketTag

    tags = list(TicketTag.objects.values_list("slug", "name"))
    if not tags:
        tag_block = "(no tags exist yet — return an empty tag list)"
    else:
        tag_block = "\n".join(f"- {slug}: {name}" for slug, name in tags)
    valid_slugs = {slug for slug, _ in tags}

    system_prompt = (
        "You triage inbound IT support tickets for a UK MSP. "
        "Choose a priority (one of critical, high, medium, low) and "
        "select 0-3 tag slugs from the supplied taxonomy. "
        "Critical = customer is offline / data at risk / payments down. "
        "High = serious impairment to business hours. "
        "Medium = non-blocking but should be done this week. "
        "Low = nice to have / question. "
        "Respond ONLY with a JSON object with keys: priority "
        '(string), tag_slugs (array of strings — must be a subset of the '
        "supplied slugs), reasoning (one sentence). No prose."
    )
    user_prompt = (
        f"Client: {ticket.client.name}\n"
        f"Care plan: {ticket.client.care_plan_tier}\n"
        f"Subject: {ticket.subject}\n\n"
        f"Description:\n{ticket.description or '(none)'}\n\n"
        f"Available tag slugs:\n{tag_block}"
    )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = "".join(getattr(b, "text", "") for b in msg.content).strip()
    # Tolerate stray ```json fences just in case.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("triage: claude returned non-JSON: %r", raw[:200])
        return None
    priority = data.get("priority")
    if priority not in {"critical", "high", "medium", "low"}:
        return None
    tag_slugs = [s for s in (data.get("tag_slugs") or []) if s in valid_slugs]
    reasoning = (data.get("reasoning") or "")[:500]
    return {"priority": priority, "tag_slugs": tag_slugs, "reasoning": reasoning}


def _claude_summarise(ticket) -> str:
    from anthropic import Anthropic

    notes = ticket.notes.select_related("author").order_by("created_at")
    history_lines = []
    for note in notes:
        who = (
            "Client"
            if note.author and getattr(note.author, "is_client", False)
            else "Engineer"
        )
        tag = " (internal)" if note.internal else ""
        history_lines.append(f"{who}{tag}: {note.body.strip()}")
    history = "\n\n".join(history_lines) or "(no notes yet)"

    system_prompt = (
        "You are summarising an IT support ticket conversation for a "
        "UK MSP engineer who is about to triage it. Produce at most 6 "
        "short bullets. Lead with the current state, then key facts "
        "(what was tried, what worked / didn't), then the open "
        "question. Use markdown bullet syntax (- ). No preamble. No "
        "closing summary line."
    )
    user_prompt = (
        f"Ticket #{ticket.pk}: {ticket.subject}\n"
        f"Client: {ticket.client.name}\n"
        f"Status: {ticket.get_status_display()}\n"
        f"Priority: {ticket.get_priority_display()}\n\n"
        f"Description:\n{ticket.description or '(none)'}\n\n"
        f"Conversation:\n{history}"
    )

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(getattr(b, "text", "") for b in msg.content).strip()


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
