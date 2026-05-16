"""Claude-powered KB article suggestions.

`suggest_articles(subject, description)` returns up to N relevant
articles. Uses Anthropic's Claude when ANTHROPIC_API_KEY is set;
otherwise falls back to keyword-overlap scoring so dev and CI work
offline. Either path is non-raising — exceptions become an empty list.

The corpus is shipped as a system block with prompt caching enabled
so repeated suggestion calls within a 5-minute window hit cache.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.db.models import Q

from .models import Article

logger = logging.getLogger(__name__)


@dataclass
class Suggestion:
    article: Article
    snippet: str
    reason: str


def _snippet(text: str, limit: int = 160) -> str:
    text = (text or "").strip().replace("\n", " ")
    return (text[:limit] + "…") if len(text) > limit else text


def suggest_articles(
    subject: str,
    description: str,
    *,
    limit: int = 3,
    client_visible_only: bool = False,
) -> list[Suggestion]:
    """Return up to `limit` likely-relevant KB articles."""
    text = f"{subject}\n{description}".strip()
    if not text:
        return []

    if getattr(settings, "ANTHROPIC_API_KEY", ""):
        try:
            return _claude_suggest(text, limit=limit, client_visible_only=client_visible_only)
        except Exception:
            logger.exception(
                "KB suggestion via Claude failed — falling back to keyword search"
            )
    return _keyword_suggest(text, limit=limit, client_visible_only=client_visible_only)


# ----- keyword fallback ------------------------------------------------


def _keyword_suggest(text: str, *, limit: int, client_visible_only: bool) -> list[Suggestion]:
    tokens = {t.strip(".,?!:;").lower() for t in text.split() if len(t) > 3}
    if not tokens:
        return []

    q = Q()
    for tok in list(tokens)[:8]:
        q |= Q(title__icontains=tok) | Q(content__icontains=tok)

    base = (
        Article.objects.visible_to_clients()
        if client_visible_only
        else Article.objects.published()
    )
    articles = list(base.filter(q)[:limit * 3])

    def score(a: Article) -> int:
        body = (a.title + " " + a.content).lower()
        return sum(1 for t in tokens if t in body)

    articles.sort(key=score, reverse=True)
    return [
        Suggestion(article=a, snippet=_snippet(a.content), reason="Keyword match")
        for a in articles[:limit]
    ]


# ----- Claude path -----------------------------------------------------


def _claude_suggest(text: str, *, limit: int, client_visible_only: bool) -> list[Suggestion]:
    from anthropic import Anthropic

    base = (
        Article.objects.visible_to_clients()
        if client_visible_only
        else Article.objects.published()
    )
    articles = list(base)
    if not articles:
        return []

    corpus_parts = [
        f"slug: {a.slug}\ntitle: {a.title}\n\n{a.content[:2000]}"
        for a in articles
    ]
    corpus = "\n\n---\n\n".join(corpus_parts)

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": (
                    "You help a support engineer pick which knowledge-base "
                    "articles are relevant to a customer's ticket. Reply ONLY "
                    "with JSON of the form "
                    '{"suggestions":[{"slug":"...","reason":"why it helps"}]}. '
                    "Up to "
                    f"{limit} entries, ranked best first. If nothing is "
                    "relevant, return an empty list."
                ),
            },
            {
                "type": "text",
                "text": f"Knowledge base corpus:\n\n{corpus}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[
            {
                "role": "user",
                "content": f"Ticket text:\n\n{text}",
            }
        ],
    )

    raw = "".join(getattr(b, "text", "") for b in msg.content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Claude returned non-JSON: %r", raw[:200])
        return []

    by_slug = {a.slug: a for a in articles}
    out: list[Suggestion] = []
    for item in (data.get("suggestions") or [])[:limit]:
        slug = (item.get("slug") or "").strip()
        a = by_slug.get(slug)
        if a is None:
            continue
        out.append(
            Suggestion(
                article=a,
                snippet=_snippet(a.content),
                reason=(item.get("reason") or "")[:200],
            )
        )
    return out
