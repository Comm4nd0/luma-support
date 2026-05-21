"""Ticket, TimeEntry, Attachment, TicketNote, CsatResponse.

The Ticket model owns the SLA deadline computation and the
status-transition timestamps (resolved_at / closed_at).
"""
import calendar
import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from .sla import deadline_for


def _csat_token() -> str:
    """URL-safe random token for one-shot CSAT links."""
    return secrets.token_urlsafe(32)


class TicketTemplate(models.Model):
    """Reusable canned reply / note body.

    Use case: Marco hits the same phrasing again and again ("we're
    scheduling your UniFi firmware update on Tuesday", "please power
    cycle the router and let us know if it recurs"). Templates are
    inserted into the note compose box on web + mobile and can opt-in
    to defaulting the resulting note to public (client-visible).
    """

    name = models.CharField(max_length=120, unique=True)
    body = models.TextField()
    public_default = models.BooleanField(
        default=True,
        help_text=(
            "When inserted, default the note's 'internal' checkbox to OFF "
            "(so the client sees the reply). Disable for engineer-only "
            "scratchpads."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TicketTag(models.Model):
    """Lightweight, free-form ticket categorisation.

    Used for slicing dashboards ("show me all UniFi tickets") and as the
    feature surface that 1.5 bulk-actions and 5.1 AI triage both write
    to. Slug is the stable wire identifier so AI / inbound integrations
    can attach tags by name without needing to hit the API for IDs first.
    """

    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)
    color = models.CharField(
        max_length=7,
        default="#14b8a6",
        help_text="Hex colour with leading # — used to tint the pill.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def _add_months(d: date, months: int) -> date:
    """Add `months` calendar months to `d`, clamping the day for short months."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class TicketQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])

    def sla_warnings(self, threshold_minutes: int = 30):
        """Open tickets within `threshold_minutes` of breaching SLA, or already breached.

        Tickets in WAITING status are paused (see ``Ticket.is_paused``) and
        are excluded so the engineer isn't punished for client wait time.
        """
        now = timezone.now()
        cutoff = now + timedelta(minutes=threshold_minutes)
        return (
            self.open()
            .filter(sla_paused_at__isnull=True)
            .filter(sla_deadline__lte=cutoff)
            .order_by("sla_deadline")
        )


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
    # When non-null, the ticket is "paused" — typically because we're
    # waiting on the customer. The displayed deadline freezes and any
    # SLA warnings stop firing until the ticket leaves WAITING, at
    # which point ``sla_deadline`` is moved forward by however long the
    # ticket was paused.
    sla_paused_at = models.DateTimeField(null=True, blank=True)

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

    tags = models.ManyToManyField(
        "TicketTag", blank=True, related_name="tickets"
    )

    # Cached Claude-generated thread summary. Invalidated by the
    # post_save signal on TicketNote so a stale summary never lingers
    # after new conversation.
    ai_summary = models.TextField(blank=True)
    ai_summary_at = models.DateTimeField(null=True, blank=True)

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

        # SLA pause bookkeeping. Entering WAITING freezes the deadline by
        # stamping ``sla_paused_at``. Leaving WAITING shifts the stored
        # deadline forward by the paused interval and clears the stamp.
        now = timezone.now()
        if first_save:
            if self.status == self.Status.WAITING and self.sla_paused_at is None:
                self.sla_paused_at = now
        else:
            old = type(self).objects.only("status", "sla_paused_at").filter(pk=self.pk).first()
            if old is not None:
                entering_waiting = (
                    self.status == self.Status.WAITING
                    and old.status != self.Status.WAITING
                )
                leaving_waiting = (
                    old.status == self.Status.WAITING
                    and self.status != self.Status.WAITING
                )
                if entering_waiting and self.sla_paused_at is None:
                    self.sla_paused_at = now
                elif leaving_waiting and self.sla_paused_at is not None:
                    if self.sla_deadline is not None:
                        self.sla_deadline = self.sla_deadline + (now - self.sla_paused_at)
                    self.sla_paused_at = None

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
    def is_paused(self) -> bool:
        return self.sla_paused_at is not None

    @property
    def effective_sla_deadline(self):
        """Deadline adjusted for in-progress pause time.

        While paused, the stored ``sla_deadline`` is frozen; the displayed
        deadline shifts forward by the wall-clock interval since the pause
        started, which keeps the visible countdown stationary. Once the
        ticket leaves WAITING, ``save()`` bakes the interval into
        ``sla_deadline`` and clears ``sla_paused_at``.
        """
        if self.sla_deadline is None:
            return None
        if self.sla_paused_at is None:
            return self.sla_deadline
        return self.sla_deadline + (timezone.now() - self.sla_paused_at)

    @property
    def is_breached(self) -> bool:
        if self.is_paused:
            return False
        eff = self.effective_sla_deadline
        return (
            eff is not None
            and self.status not in (self.Status.RESOLVED, self.Status.CLOSED)
            and timezone.now() > eff
        )

    @property
    def time_remaining(self):
        eff = self.effective_sla_deadline
        if not eff:
            return None
        return eff - timezone.now()

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


class MaintenanceSchedule(models.Model):
    """Recurring maintenance work for a care-plan client.

    The `generate_scheduled_tickets` Celery beat task creates a Ticket
    from this template whenever `next_run_at <= today`, then advances
    `next_run_at` by one cadence interval. Overdue schedules catch up
    in a loop so a never-handled row doesn't fire a new ticket per day
    indefinitely.
    """

    class Cadence(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        BIANNUAL = "biannual", "Every 6 months"
        ANNUAL = "annual", "Annual"

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="maintenance_schedules",
    )
    system = models.ForeignKey(
        "clients.System",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_schedules",
    )
    cadence = models.CharField(max_length=16, choices=Cadence.choices)
    next_run_at = models.DateField()
    template_subject = models.CharField(max_length=300)
    template_description = models.TextField(blank=True)
    # Blank = let Ticket._auto_priority pick from the client's care-plan tier.
    priority = models.CharField(
        max_length=16, choices=Ticket.Priority.choices, blank=True
    )
    default_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    active = models.BooleanField(default=True)
    last_run_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_run_at", "id"]
        indexes = [models.Index(fields=["active", "next_run_at"])]

    def __str__(self):
        return f"{self.client.name} — {self.template_subject} ({self.cadence})"

    def compute_next_run_at(self, from_date: date | None = None) -> date:
        base = from_date or self.next_run_at
        c = self.cadence
        if c == self.Cadence.WEEKLY:
            return base + timedelta(days=7)
        if c == self.Cadence.MONTHLY:
            return _add_months(base, 1)
        if c == self.Cadence.QUARTERLY:
            return _add_months(base, 3)
        if c == self.Cadence.BIANNUAL:
            return _add_months(base, 6)
        if c == self.Cadence.ANNUAL:
            return _add_months(base, 12)
        # Unknown cadence — fall back to weekly so we don't hang the task.
        return base + timedelta(days=7)


class CsatResponse(models.Model):
    """One-shot CSAT survey attached to a ticket.

    Created (pending, no rating) when the ticket transitions to CLOSED
    and the client gets emailed a tokenized link to /csat/<token>/.
    The link is single-use: once `rating` is set, the form rejects
    further submissions for the same token.
    """

    ticket = models.OneToOneField(
        Ticket, on_delete=models.CASCADE, related_name="csat"
    )
    token = models.CharField(max_length=64, unique=True, default=_csat_token)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"CSAT #{self.ticket_id} ({self.rating or 'pending'})"
