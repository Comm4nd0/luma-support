"""Thin helpers around AuditLog so callers don't reach into the model.

`log()` is intentionally forgiving — it swallows its own exceptions so
audit-write failures never break the real flow. Failures are logged.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def log(
    action: str,
    *,
    actor: Optional[Any] = None,
    target: Optional[Any] = None,
    request: Optional[Any] = None,
    **metadata: Any,
):
    """Drop an AuditLog row and return it (or None on failure).

    Args:
        action: short identifier like "xero.connect" or "invoice.send".
        actor: optional User. Inferred from `request.user` when omitted.
        target: optional model instance — its content_type + pk get stored
            so we can render a link, plus `str(target)` for display.
        request: optional HttpRequest used to capture IP and user-agent.
        **metadata: arbitrary JSON-serialisable extras.
    """
    try:
        from .models import AuditLog
        from django.contrib.contenttypes.models import ContentType

        kwargs: dict[str, Any] = {"action": action, "metadata": metadata}
        if request is not None:
            kwargs["ip"] = _client_ip(request)
            kwargs["user_agent"] = request.META.get("HTTP_USER_AGENT", "")[:255]
            if actor is None:
                user = getattr(request, "user", None)
                if user is not None and getattr(user, "is_authenticated", False):
                    actor = user
        if actor is not None:
            kwargs["actor"] = actor
        if target is not None:
            kwargs["target_ct"] = ContentType.objects.get_for_model(target)
            kwargs["target_id"] = target.pk
            kwargs["target_repr"] = str(target)[:255]
        return AuditLog.objects.create(**kwargs)
    except Exception:
        logger.exception("audit.log failed: action=%s", action)
        return None


def _client_ip(request) -> Optional[str]:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
