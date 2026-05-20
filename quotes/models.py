"""Quote / proposal models.

A `Quote` is a draft contract sent to a Lead or an existing Client
before any invoice exists. The QuoteLine shape mirrors
`billing.InvoiceLine` 1:1 so the accept flow can copy lines straight
into a DRAFT Invoice (see `quotes.services.create_invoice_from_quote`).

The accept link is a single-use tokenised URL — the same pattern used
by `tickets.CsatResponse` — so a prospect can confirm acceptance
without needing an account.
"""
from __future__ import annotations

import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def _accept_token() -> str:
    return secrets.token_urlsafe(32)


def _default_valid_until() -> date:
    return timezone.localdate() + timedelta(days=30)


class QuoteStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    EXPIRED = "expired", "Expired"


class Quote(models.Model):
    number = models.CharField(max_length=32, unique=True, blank=True)

    lead = models.ForeignKey(
        "leads.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    client = models.ForeignKey(
        "clients.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )

    status = models.CharField(
        max_length=16, choices=QuoteStatus.choices, default=QuoteStatus.DRAFT
    )
    valid_until = models.DateField(default=_default_valid_until)

    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    tax = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    currency = models.CharField(max_length=3, default="GBP")
    notes = models.TextField(blank=True)

    # Public, single-use accept link.
    accept_token = models.CharField(
        max_length=64, unique=True, default=_accept_token
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by_name = models.CharField(max_length=200, blank=True)
    accepted_ip = models.CharField(max_length=64, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=200, blank=True)

    converted_invoice = models.ForeignKey(
        "billing.Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="origin_quotes",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes_created",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.number or f"Quote #{self.pk}"

    @property
    def recipient_name(self) -> str:
        if self.client_id:
            return self.client.name
        if self.lead_id:
            return self.lead.name
        return ""

    @property
    def recipient_email(self) -> str:
        if self.client_id:
            return self.client.email
        if self.lead_id:
            return self.lead.email
        return ""

    @property
    def is_expired(self) -> bool:
        return (
            self.status in (QuoteStatus.DRAFT, QuoteStatus.SENT)
            and self.valid_until is not None
            and self.valid_until < timezone.localdate()
        )

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = _next_quote_number()
        super().save(*args, **kwargs)

    def recalculate_totals(self) -> None:
        """Sum line_total values. Tax stays at whatever the operator entered."""
        subtotal = sum(
            (line.line_total for line in self.lines.all()),
            Decimal("0"),
        )
        self.subtotal = subtotal
        self.total = subtotal + (self.tax or Decimal("0"))


class QuoteLine(models.Model):
    quote = models.ForeignKey(
        Quote, on_delete=models.CASCADE, related_name="lines"
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    account_code = models.CharField(max_length=16, blank=True)
    tax_type = models.CharField(max_length=24, blank=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.description} ({self.quantity} × {self.unit_amount})"

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal("0")) * (
            self.unit_amount or Decimal("0")
        )
        super().save(*args, **kwargs)


def _next_quote_number() -> str:
    """Return the next Q-YYYY-NNNN identifier for the current year.

    Sequential within the calendar year, four-digit zero-padded.
    Not strictly race-free for concurrent creates — fine for a one-
    person business where Marco is unlikely to raise two quotes at
    the same millisecond.
    """
    year = timezone.localdate().year
    prefix = f"Q-{year}-"
    last = (
        Quote.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    n = 1
    if last:
        try:
            n = int(last.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            n = 1
    return f"{prefix}{n:04d}"
