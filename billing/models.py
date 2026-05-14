"""Invoicing, payments and Xero connection state."""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from clients.encryption import decrypt, encrypt


class XeroConnection(models.Model):
    """Single-row table holding the OAuth tokens for Marco's Xero org."""

    tenant_id = models.CharField(max_length=64)
    refresh_token_encrypted = models.TextField()
    access_token = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    connected_at = models.DateTimeField(auto_now_add=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        verbose_name = "Xero connection"

    def __str__(self) -> str:
        return f"Xero({self.tenant_id})"

    def save(self, *args, **kwargs):
        # Enforce singleton — there is only one Xero org connected.
        self.pk = 1
        existing = type(self).objects.filter(pk=1).only("connected_at").first()
        if existing is not None:
            self.connected_at = existing.connected_at
            self._state.adding = False
        super().save(*args, **kwargs)

    def set_refresh_token(self, plaintext: str) -> None:
        self.refresh_token_encrypted = encrypt(plaintext)

    def get_refresh_token(self) -> str:
        return decrypt(self.refresh_token_encrypted)


class Invoice(models.Model):
    class Kind(models.TextChoices):
        ONE_OFF = "one_off", "One-off"
        CONTRACT = "contract", "Contract"
        TIME = "time", "Time-based"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        AUTHORISED = "authorised", "Authorised"
        PAID = "paid", "Paid"
        VOIDED = "voided", "Voided"

    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="invoices"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="GBP")
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    xero_invoice_id = models.CharField(max_length=64, blank=True)
    xero_status = models.CharField(max_length=24, blank=True)
    xero_synced_at = models.DateTimeField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices_created",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "kind", "period_start"],
                condition=Q(kind="contract"),
                name="uniq_contract_invoice_per_period",
            ),
        ]

    def __str__(self) -> str:
        return f"Invoice #{self.pk} — {self.client.name}"

    def recalculate_totals(self) -> None:
        """Sum line_total values; tax is set by Xero on push so kept at 0 locally."""
        subtotal = sum(
            (line.line_total for line in self.lines.all()),
            Decimal("0"),
        )
        self.subtotal = subtotal
        self.total = subtotal + (self.tax or Decimal("0"))


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="lines"
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    account_code = models.CharField(max_length=16, blank=True)
    tax_type = models.CharField(max_length=24, blank=True)
    time_entry = models.ForeignKey(
        "tickets.TimeEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self) -> str:
        return f"{self.description} ({self.quantity} × {self.unit_amount})"

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal("0")) * (
            self.unit_amount or Decimal("0")
        )
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Read-only mirror of payments seen on Xero invoices."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    xero_payment_id = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"Payment {self.xero_payment_id} ({self.amount})"
