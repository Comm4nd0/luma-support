"""GDPR / right-of-access helpers.

``export_client(client)`` returns a JSON-serialisable dict that
captures every piece of data Luma holds about a single client. It's
sized for "drop into a download", not for incremental sync; the
caller wraps it in an HTTP response or writes it to disk.

Sensitive fields (encrypted credentials, recovery code hashes) are
*deliberately not included* — exporting them would defeat the
purpose of encrypting them in the first place.
"""
from __future__ import annotations

from typing import Any

from .models import Client


def export_client(client: Client) -> dict[str, Any]:
    from billing.models import Invoice
    from notifications.models import Notification
    from tickets.models import CsatResponse, Ticket

    def _ts(value):
        return value.isoformat() if value else None

    return {
        "client": {
            "id": client.pk,
            "name": client.name,
            "company": client.company,
            "email": client.email,
            "phone": client.phone,
            "address": client.address,
            "vat_number": getattr(client, "vat_number", ""),
            "care_plan_tier": client.care_plan_tier,
            "care_plan_start": _ts(client.care_plan_start),
            "care_plan_renewal": _ts(client.care_plan_renewal),
            "monthly_fee": str(client.monthly_fee or ""),
            "hourly_rate": str(client.hourly_rate or ""),
            "notes": client.notes,
            "created_at": _ts(client.created_at),
        },
        "contacts": [
            {
                "id": c.pk,
                "name": c.name,
                "email": c.email,
                "phone": c.phone,
                "title": c.title,
                "is_primary": c.is_primary,
                "created_at": _ts(c.created_at),
            }
            for c in client.contacts.all()
        ],
        "systems": [
            {
                "id": s.pk,
                "name": s.name,
                "type": s.type,
                "description": s.description,
                "installed_date": _ts(s.installed_date),
                "monitoring_url": s.monitoring_url,
                "credentials_present": bool(s.credentials_encrypted),
            }
            for s in client.systems.all()
        ],
        "tickets": [
            {
                "id": t.pk,
                "subject": t.subject,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
                "sla_deadline": _ts(t.sla_deadline),
                "created_at": _ts(t.created_at),
                "resolved_at": _ts(t.resolved_at),
                "closed_at": _ts(t.closed_at),
                "notes": [
                    {
                        "id": n.pk,
                        "author_email": getattr(n.author, "email", None),
                        "internal": n.internal,
                        "body": n.body,
                        "created_at": _ts(n.created_at),
                    }
                    for n in t.notes.all()
                ],
                "time_entries": [
                    {
                        "id": te.pk,
                        "minutes": te.minutes,
                        "description": te.description,
                        "billable": te.billable,
                        "user_email": getattr(te.user, "email", None),
                        "created_at": _ts(te.created_at),
                    }
                    for te in t.time_entries.all()
                ],
            }
            for t in Ticket.objects.filter(client=client)
                                   .prefetch_related(
                                       "notes__author", "time_entries__user"
                                   )
        ],
        "csat_responses": [
            {
                "ticket_id": csat.ticket_id,
                "rating": csat.rating,
                "comment": csat.comment,
                "requested_at": _ts(csat.requested_at),
                "responded_at": _ts(csat.responded_at),
            }
            for csat in CsatResponse.objects.filter(ticket__client=client)
        ],
        "invoices": [
            {
                "id": inv.pk,
                "kind": inv.kind,
                "status": inv.status,
                "subtotal": str(inv.subtotal),
                "tax": str(inv.tax),
                "total": str(inv.total),
                "currency": inv.currency,
                "due_date": _ts(inv.due_date),
                "created_at": _ts(inv.created_at),
                "paid_at": _ts(inv.paid_at),
            }
            for inv in Invoice.objects.filter(client=client)
        ],
        "documents": [
            {
                "id": d.pk,
                "title": d.title,
                "kind": d.kind,
                "uploaded_at": _ts(d.uploaded_at),
                "uploaded_by_email": getattr(d.uploaded_by, "email", None),
            }
            for d in client.documents.select_related("uploaded_by")
        ],
        "site_visits": [
            {
                "id": v.pk,
                "user_email": getattr(v.user, "email", None),
                "started_at": _ts(v.started_at),
                "ended_at": _ts(v.ended_at),
                "lat_start": str(v.lat_start) if v.lat_start else None,
                "lon_start": str(v.lon_start) if v.lon_start else None,
                "lat_end": str(v.lat_end) if v.lat_end else None,
                "lon_end": str(v.lon_end) if v.lon_end else None,
                "notes": v.notes,
                "duration_minutes": v.duration_minutes,
            }
            for v in client.site_visits.select_related("user")
        ],
        "notifications": [
            {
                "id": n.pk,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "created_at": _ts(n.created_at),
            }
            for n in Notification.objects.filter(
                user__client=client
            ).select_related("user")
        ],
    }


def forget_client(client: Client) -> dict[str, int]:
    """Pseudonymise a client (right-to-be-forgotten).

    We don't hard-delete because every ticket / invoice / audit row
    is also history we have to keep for tax + lessons-learned reasons.
    Instead we wipe the personally-identifying fields and break the
    user→client link on portal accounts.

    Returns a count of touched rows per category. Caller should write
    an audit row.
    """
    from accounts.models import User

    touched = {
        "contacts": 0, "documents": 0, "users_unlinked": 0,
    }

    for contact in client.contacts.all():
        contact.name = f"[redacted #{contact.pk}]"
        contact.email = ""
        contact.phone = ""
        contact.save(update_fields=["name", "email", "phone"])
        touched["contacts"] += 1

    for doc in client.documents.all():
        doc.delete()
        touched["documents"] += 1

    for user in User.objects.filter(client=client):
        user.client = None
        user.is_active = False
        user.save(update_fields=["client", "is_active"])
        touched["users_unlinked"] += 1

    client.name = f"[redacted #{client.pk}]"
    client.company = ""
    client.email = ""
    client.phone = ""
    client.address = ""
    client.notes = "[redacted]"
    client.save(update_fields=["name", "company", "email", "phone",
                                "address", "notes"])
    return touched
