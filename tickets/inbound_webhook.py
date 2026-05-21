"""Generic webhook ingest — POST JSON, get a Ticket.

Mounted at ``/api/v1/tickets/webhook/<token>/``. Auth is by URL token
(``IngestEndpoint.token``) rather than session/JWT because the callers
(Grafana, Uptime Kuma, Sentry, GitHub Actions, …) ship simple webhook
configs — token in the URL is the practical lowest-friction option.
Tokens are 32-byte secrets and the URL is HTTPS-only on production.
"""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import IngestEndpoint, Ticket


@csrf_exempt
@require_POST
def webhook_ingest(request, token):
    endpoint = IngestEndpoint.objects.filter(token=token, enabled=True).first()
    if endpoint is None:
        # 404 to leak as little as possible about whether the token
        # exists-but-disabled vs simply unknown.
        return JsonResponse({"detail": "not found"}, status=404)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        endpoint.last_status = "bad-json"
        endpoint.last_called_at = timezone.now()
        endpoint.save(update_fields=["last_status", "last_called_at"])
        return JsonResponse({"detail": "invalid JSON"}, status=400)

    subject = (
        _extract(payload, endpoint.subject_field)
        or f"{endpoint.name} alert"
    )[:300]
    body = _extract(payload, endpoint.body_field)
    if not body:
        # Fall back to the raw JSON so we never silently drop signal.
        body = json.dumps(payload, indent=2, default=str)[:4000]

    ticket = Ticket.objects.create(
        client=endpoint.client,
        subject=subject,
        description=body,
        priority=endpoint.default_priority,
        assigned_to=endpoint.default_assignee,
    )
    endpoint.last_status = "ok"
    endpoint.last_called_at = timezone.now()
    endpoint.save(update_fields=["last_status", "last_called_at"])
    return JsonResponse({"ticket_id": ticket.pk}, status=201)


def _extract(payload, key: str):
    """Pull ``key`` from ``payload`` — supports one level of dotted path
    so the caller can say e.g. ``alert.title`` for nested payloads."""
    if not isinstance(payload, dict) or not key:
        return None
    current = payload
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if current is None:
        return None
    if isinstance(current, (dict, list)):
        return json.dumps(current, default=str)
    return str(current)
