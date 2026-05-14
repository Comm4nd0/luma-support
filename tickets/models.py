"""Ticket, TimeEntry, Attachment, TicketNote.

The Ticket model owns the SLA deadline computation and the
status-transition timestamps (resolved_at / closed_at).
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from .sla import deadline_for


class TicketQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])

    def sla_warnings(self, threshold_minutes: int = 30):
        """Open tickets within `threshold_minutes` of breaching SLA, or already breached."""
        now = timezone.now()
        cutoff = now + timedelta(minutes=threshold_minutes)
        return self.open().filter(sla_deadline__lte=cutoff).order_by("sla_deadline")


class Ticket(models.Model):
    class Priority(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class Status(models.TextChoices):
        NEW = "new", "New"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting on client"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    client = models.ForeignKey(
        "clients.Client", on_delete=models.PROTECT, related_name="tickets"
    )
    system = models.ForeignKey(
        "clients.System",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    subject = models.CharField(max_length=300)
    description = models.TextField(blank=True)

    priority = models.CharField(
        max_length=16, choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.NEW
    )

    sla_deadline = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tickets",
    )

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TicketQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "sla_deadline"]),
            models.Index(fields=["priority", "status"]),
        ]

    def __str__(self):
        return f"#{self.pk} — {self.subject}"

    # --- lifecycle ----------------------------------------------------
    def save(self, *args, **kwargs):
        first_save = self.pk is None
        if first_save and not self.priority:
            self.priority = self._auto_priority()
        # SLA deadline is set on first save (using the to-be-created
        # timestamp) and recomputed when priority changes.
        if first_save:
            now = timezone.now()
            self.sla_deadline = deadline_for(now, self.priority)
        elif self.priority and self.sla_deadline is None:
            self.sla_deadline = deadline_for(self.created_at, self.priority)

        # Status timestamps
        if self.status == self.Status.RESOLVED and self.resolved_at is None:
            self.resolved_at = timezone.now()
        if self.status == self.Status.CLOSED and self.closed_at is None:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)

    def _auto_priority(self) -> str:
        from .sla import auto_priority_for

        return auto_priority_for(self.client.care_plan_tier)

    def transition_to(self, new_status: str, by_user=None) -> None:
        self.status = new_status
        if new_status == self.Status.ASSIGNED and by_user and not self.assigned_to:
            self.assigned_to = by_user
        self.save()

    # --- SLA helpers --------------------------------------------------
    @property
    def is_breached(self) -> bool:
        return (
            self.sla_deadline is not None
            and self.status not in (self.Status.RESOLVED, self.Status.CLOSED)
            and timezone.now() > self.sla_deadline
        )

    @property
    def time_remaining(self):
        if not self.sla_deadline:
            return None
        return self.sla_deadline - timezone.now()

    @property
    def total_minutes_logged(self) -> int:
        return self.time_entries.aggregate(total=models.Sum("minutes"))["total"] or 0


class TimeEntry(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="time_entries"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="time_entries",
    )
    minutes = models.PositiveIntegerField()
    description = models.CharField(max_length=500, blank=True)
    billable = models.BooleanField(default=True)

    invoice_line = models.ForeignKey(
        "billing.InvoiceLine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.minutes}m on #{self.ticket_id}"

    def hours(self) -> Decimal:
        return (Decimal(self.minutes) / Decimal(60)).quantize(Decimal("0.01"))

    def cost(self) -> Decimal:
        rate = self.ticket.client.effective_hourly_rate()
        return (self.hours() * rate).quantize(Decimal("0.01"))


def attachment_upload_path(instance, filename):
    return f"tickets/{instance.ticket_id}/{filename}"


class Attachment(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=attachment_upload_path)
    filename = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_attachments",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def save(self, *args, **kwargs):
        if not self.filename and self.file:
            self.filename = self.file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.filename or f"Attachment {self.pk}"


class TicketNote(models.Model):
    """Engineer notes on a ticket. `internal=True` hides the note from clients."""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="notes"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="ticket_notes",
    )
    body = models.TextField()
    internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Note on #{self.ticket_id} by {self.author_id}"
