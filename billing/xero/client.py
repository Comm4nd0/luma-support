"""Thin Xero Accounting API wrapper around httpx."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from django.utils import timezone

from ..models import Invoice, XeroConnection
from . import oauth

API_BASE = "https://api.xero.com/api.xro/2.0"


class XeroClient:
    def __init__(self, connection: XeroConnection):
        self.conn = connection

    # --- token management -------------------------------------------------
    def _ensure_fresh_token(self) -> None:
        if self.conn.expires_at - timezone.now() > timedelta(seconds=60):
            return
        data = oauth.refresh(self.conn.get_refresh_token())
        self.conn.access_token = data["access_token"]
        self.conn.expires_at = timezone.now() + timedelta(seconds=int(data["expires_in"]))
        # Xero rotates the refresh token on every refresh — persist or future
        # refreshes will fail.
        self.conn.set_refresh_token(data["refresh_token"])
        self.conn.save()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.conn.access_token}",
            "Xero-tenant-id": self.conn.tenant_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # --- contacts ---------------------------------------------------------
    def upsert_contact(self, client) -> str:
        """Create or update a Xero Contact for `client`; return its ContactID."""
        self._ensure_fresh_token()
        payload = {
            "Name": client.company or client.name,
            "FirstName": client.name,
            "EmailAddress": client.email or "",
        }
        if client.vat_number:
            payload["TaxNumber"] = client.vat_number
        if client.effective_billing_address:
            payload["Addresses"] = [
                {
                    "AddressType": "POBOX",
                    "AddressLine1": client.effective_billing_address[:500],
                }
            ]
        if client.xero_contact_id:
            payload["ContactID"] = client.xero_contact_id

        resp = httpx.post(
            f"{API_BASE}/Contacts",
            headers=self._headers(),
            json={"Contacts": [payload]},
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        contact_id = data["Contacts"][0]["ContactID"]
        if client.xero_contact_id != contact_id:
            client.xero_contact_id = contact_id
        client.xero_synced_at = timezone.now()
        client.save(update_fields=["xero_contact_id", "xero_synced_at"])
        return contact_id

    # --- invoices ---------------------------------------------------------
    def create_invoice(self, invoice: Invoice, *, status: str = "AUTHORISED") -> dict:
        """Create the invoice in Xero. Returns the Xero JSON for invoice[0]."""
        self._ensure_fresh_token()
        contact_id = invoice.client.xero_contact_id or self.upsert_contact(
            invoice.client
        )
        line_items = [
            {
                "Description": line.description,
                "Quantity": str(line.quantity),
                "UnitAmount": str(line.unit_amount),
                "AccountCode": line.account_code or "",
                "TaxType": line.tax_type or "",
            }
            for line in invoice.lines.all()
        ]
        payload = {
            "Type": "ACCREC",
            "Contact": {"ContactID": contact_id},
            "LineItems": line_items,
            "LineAmountTypes": "Exclusive",
            "CurrencyCode": invoice.currency,
            "Status": status,
        }
        if invoice.due_date:
            payload["DueDate"] = invoice.due_date.isoformat()
        if invoice.notes:
            payload["Reference"] = invoice.notes[:255]

        resp = httpx.post(
            f"{API_BASE}/Invoices",
            headers=self._headers(),
            json={"Invoices": [payload]},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()["Invoices"][0]
        invoice.xero_invoice_id = data["InvoiceID"]
        invoice.xero_status = data.get("Status", "")
        invoice.xero_synced_at = timezone.now()
        invoice.sent_at = timezone.now()
        invoice.status = (
            Invoice.Status.AUTHORISED if status == "AUTHORISED" else Invoice.Status.SENT
        )
        if "TotalTax" in data:
            invoice.tax = Decimal(str(data["TotalTax"]))
        if "Total" in data:
            invoice.total = Decimal(str(data["Total"]))
        invoice.save()
        return data

    def list_payments(self, since: datetime) -> list[dict]:
        self._ensure_fresh_token()
        # Xero "If-Modified-Since" header is the standard way to filter.
        headers = self._headers()
        headers["If-Modified-Since"] = since.astimezone(UTC).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        resp = httpx.get(
            f"{API_BASE}/Payments",
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("Payments", [])


def parse_xero_datetime(raw: str) -> datetime:
    """Xero returns .NET-style /Date(1700000000000+0000)/ in some payloads."""
    if raw.startswith("/Date("):
        inner = raw[6:-2]
        # Strip timezone suffix like +0000 if present.
        for sep in ("+", "-"):
            idx = inner.rfind(sep)
            if idx > 0:
                inner = inner[:idx]
                break
        return datetime.fromtimestamp(int(inner) / 1000, tz=UTC)
    # ISO-8601 fallback.
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
