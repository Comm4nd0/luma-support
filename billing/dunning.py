"""Read-only helper for surfacing the audit-driven dunning timeline.

``chase_overdue_invoices`` writes one ``invoice.dunning`` AuditLog row
per (invoice, bucket) — see billing/tasks.py. This helper folds those
rows into a list, newest first, so the invoice detail page can render
the timeline without each call site re-deriving the query.
"""
from __future__ import annotations

from typing import Iterable

from django.contrib.contenttypes.models import ContentType

from audit.models import AuditLog

from .models import Invoice


def dunning_events_for(invoice: Invoice) -> Iterable[AuditLog]:
    inv_ct = ContentType.objects.get_for_model(Invoice)
    return (
        AuditLog.objects.filter(
            action="invoice.dunning",
            target_ct=inv_ct,
            target_id=invoice.pk,
        )
        .order_by("-created_at")
    )
