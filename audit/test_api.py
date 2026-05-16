"""/api/v1/audit/logs/ — admin-only feed."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_audit_api_requires_admin(engineer_user):
    AuditLog.objects.create(action="x.y")
    c = APIClient()
    c.force_authenticate(engineer_user)
    resp = c.get("/api/v1/audit/logs/")
    assert resp.status_code == 403


def test_audit_api_lists_for_admin(admin_user):
    AuditLog.objects.create(action="xero.connect", actor=admin_user)
    AuditLog.objects.create(action="invoice.send_to_xero", actor=admin_user)
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.get("/api/v1/audit/logs/")
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()["results"]}
    assert {"xero.connect", "invoice.send_to_xero"} <= actions


def test_audit_api_filters_by_action(admin_user):
    AuditLog.objects.create(action="xero.connect")
    AuditLog.objects.create(action="invoice.send_to_xero")
    c = APIClient()
    c.force_authenticate(admin_user)
    resp = c.get("/api/v1/audit/logs/?action=xero.connect")
    assert resp.status_code == 200
    actions = {e["action"] for e in resp.json()["results"]}
    assert actions == {"xero.connect"}
