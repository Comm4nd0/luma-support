"""Tests for the audit log helper, viewer, and Xero/billing integration points."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client as DjangoClient
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from audit import log as audit_log
from audit.models import AuditLog

pytestmark = pytest.mark.django_db


# ----- helper -----------------------------------------------------------


def test_log_creates_row_with_request_context(admin_user):
    rf = RequestFactory()
    request = rf.get("/", HTTP_X_FORWARDED_FOR="203.0.113.5, 10.0.0.1",
                     HTTP_USER_AGENT="Mozilla/5.0 test")
    request.user = admin_user

    entry = audit_log("test.action", request=request, foo="bar")

    assert entry is not None
    assert entry.action == "test.action"
    assert entry.actor == admin_user
    assert entry.ip == "203.0.113.5"
    assert "test" in entry.user_agent
    assert entry.metadata == {"foo": "bar"}


def test_log_records_target_via_generic_fk(admin_user, client_record):
    entry = audit_log("client.touched", actor=admin_user, target=client_record)
    assert entry.target == client_record
    assert entry.target_repr == client_record.name
    assert entry.target_ct.model == "client"


def test_log_swallows_exceptions(admin_user, monkeypatch):
    """An audit-write failure must not propagate to the caller."""

    def boom(**kwargs):
        raise RuntimeError("DB on fire")

    monkeypatch.setattr(AuditLog.objects, "create", boom)
    # Should not raise.
    assert audit_log("test.boom", actor=admin_user) is None


def test_log_anonymous_request_has_no_actor():
    from django.contrib.auth.models import AnonymousUser

    rf = RequestFactory()
    request = rf.get("/")
    request.user = AnonymousUser()
    entry = audit_log("anon.thing", request=request)
    assert entry.actor is None


# ----- billing integration points --------------------------------------


def test_xero_disconnect_writes_audit_row(admin_user):
    from datetime import timedelta

    from billing.models import XeroConnection

    conn = XeroConnection(
        tenant_id="tenant-x",
        access_token="at",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    conn.set_refresh_token("rt")
    conn.save()

    client = DjangoClient()
    client.force_login(admin_user)
    client.post("/billing/xero/disconnect/")

    entry = AuditLog.objects.filter(action="xero.disconnect").get()
    assert entry.actor == admin_user
    assert entry.metadata["tenant_id"] == "tenant-x"


def test_invoice_send_writes_audit_row(admin_user, monkeypatch):
    from decimal import Decimal

    from billing.models import Invoice, InvoiceLine, XeroConnection
    from clients.models import CarePlanTier, Client

    c = Client.objects.create(name="Acme", care_plan_tier=CarePlanTier.PROFESSIONAL)
    inv = Invoice.objects.create(client=c, kind=Invoice.Kind.ONE_OFF, total=Decimal("75.00"))
    InvoiceLine.objects.create(
        invoice=inv, description="visit", quantity=Decimal("1"), unit_amount=Decimal("75")
    )

    conn = XeroConnection(
        tenant_id="t",
        access_token="at",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    conn.set_refresh_token("rt")
    conn.save()

    # Don't actually queue Celery / hit Xero.
    monkeypatch.setattr("billing.tasks.push_invoice_to_xero.delay", lambda *a, **kw: None)

    client = DjangoClient()
    client.force_login(admin_user)
    client.post(f"/billing/invoices/{inv.pk}/send/")

    entry = AuditLog.objects.filter(action="invoice.send_to_xero").get()
    assert entry.actor == admin_user
    assert entry.target == inv
    assert entry.metadata["currency"] == "GBP"


# ----- viewer page ------------------------------------------------------


def test_audit_page_requires_admin(engineer_user):
    AuditLog.objects.create(action="x.y")
    client = DjangoClient()
    client.force_login(engineer_user)
    resp = client.get(reverse("portal:audit_log"))
    assert resp.status_code == 403


def test_audit_page_lists_entries_for_admin(admin_user):
    AuditLog.objects.create(action="xero.connect")
    AuditLog.objects.create(action="invoice.send_to_xero")
    client = DjangoClient()
    client.force_login(admin_user)
    resp = client.get(reverse("portal:audit_log"))
    assert resp.status_code == 200
    assert b"xero.connect" in resp.content
    assert b"invoice.send_to_xero" in resp.content


def test_audit_page_filters_by_action(admin_user):
    AuditLog.objects.create(action="xero.connect")
    AuditLog.objects.create(action="invoice.send_to_xero")
    client = DjangoClient()
    client.force_login(admin_user)
    resp = client.get(reverse("portal:audit_log"), {"action": "connect"})
    assert resp.status_code == 200
    assert b"xero.connect" in resp.content
    assert b"invoice.send_to_xero" not in resp.content
