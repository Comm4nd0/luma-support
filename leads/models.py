"""Lead pipeline: prospect records and their activity timeline.

A `Lead` is everything we know about a prospect before they become a
`clients.Client`. The pipeline progresses NEW → CONTACTED → QUALIFIED →
QUOTED → WON / LOST / DORMANT. Calling `Lead.convert_to_client()` on a
WON lead creates the Client and links them.

`LeadActivity` is the prospect-side equivalent of `tickets.TicketNote`
— every call/email/meeting/note/stage change is logged so the timeline
on the lead detail page tells the full story.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from clients.models import Client, CustomerType


class LeadStage(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    QUALIFIED = "qualified", "Qualified"
    QUOTED = "quoted", "Quoted"
    WON = "won", "Won"
    LOST = "lost", "Lost"
    DORMANT = "dormant", "Dormant"


# Stages where follow-up reminders still make sense.
ACTIVE_STAGES = (
    LeadStage.NEW,
    LeadStage.CONTACTED,
    LeadStage.QUALIFIED,
    LeadStage.QUOTED,
)


class LeadSource(models.TextChoices):
    REFERRAL = "referral", "Referral"
    WEBSITE = "website", "Website"
    SOCIAL = "social", "Social"
    INBOUND_EMAIL = "inbound_email", "Inbound email"
    COLD = "cold", "Cold outreach"
    OTHER = "other", "Other"


class Lead(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    company = models.CharField(max_length=200, blank=True)

    customer_type = models.CharField(
        max_length=8, choices=CustomerType.choices, default=CustomerType.HOME
    )

    source = models.CharField(
        max_length=20, choices=LeadSource.choices, default=LeadSource.OTHER
    )
    source_detail = models.CharField(max_length=200, blank=True)
    referring_client = models.ForeignKey(
        Client,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )

    interest = models.TextField(blank=True)
    estimated_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    stage = models.CharField(
        max_length=16, choices=LeadStage.choices, default=LeadStage.NEW
    )
    next_action_at = models.DateTimeField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads_assigned",
    )

    converted_client = models.ForeignKey(
        Client,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="origin_leads",
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True)

    last_reminded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stage"]),
            models.Index(fields=["next_action_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"

    @property
    def is_active(self) -> bool:
        return self.stage in ACTIVE_STAGES

    @property
    def is_overdue(self) -> bool:
        return (
            self.is_active
            and self.next_action_at is not None
            and self.next_action_at < timezone.now()
        )

    @transaction.atomic
    def transition_to(self, new_stage: str, *, by_user=None, lost_reason: str = ""):
        """Move the lead to `new_stage` and log a STAGE_CHANGE activity.

        Caller is responsible for `convert_to_client()` if `new_stage`
        is WON — this method records the stage change but does NOT
        create a Client. Use the explicit conversion path for that.
        """
        if new_stage == self.stage:
            return
        old = self.get_stage_display()
        self.stage = new_stage
        if new_stage == LeadStage.LOST and lost_reason:
            self.lost_reason = lost_reason[:200]
        self.save(update_fields=["stage", "lost_reason", "updated_at"])
        new = self.get_stage_display()
        LeadActivity.objects.create(
            lead=self,
            kind=ActivityKind.STAGE_CHANGE,
            body=f"{old} → {new}"
            + (f" — {lost_reason}" if lost_reason else ""),
            actor=by_user,
        )

    @transaction.atomic
    def convert_to_client(self, *, by_user=None) -> Client:
        """Create (or attach) a Client for this WON lead.

        Idempotent: if `converted_client` is already set we just return
        it. Otherwise we create a new Client copying the basic fields
        across, transition to WON, and log activities.
        """
        if self.converted_client_id is not None:
            return self.converted_client

        client = Client.objects.create(
            name=self.name,
            company=self.company,
            email=self.email,
            phone=self.phone,
            customer_type=self.customer_type,
            notes=(
                f"Converted from lead #{self.pk}.\n"
                f"Source: {self.get_source_display()}"
                + (f" — {self.source_detail}" if self.source_detail else "")
                + (
                    f"\nReferred by: {self.referring_client.name}"
                    if self.referring_client
                    else ""
                )
                + (f"\nInterest: {self.interest}" if self.interest else "")
            ),
        )
        self.converted_client = client
        self.converted_at = timezone.now()
        if self.stage != LeadStage.WON:
            old = self.get_stage_display()
            self.stage = LeadStage.WON
            self.save(
                update_fields=[
                    "stage",
                    "converted_client",
                    "converted_at",
                    "updated_at",
                ]
            )
            LeadActivity.objects.create(
                lead=self,
                kind=ActivityKind.STAGE_CHANGE,
                body=f"{old} → Won (converted to client #{client.pk})",
                actor=by_user,
            )
        else:
            self.save(
                update_fields=["converted_client", "converted_at", "updated_at"]
            )
            LeadActivity.objects.create(
                lead=self,
                kind=ActivityKind.NOTE,
                body=f"Converted to client #{client.pk}",
                actor=by_user,
            )
        # Credit the referrer (if any) — pulled in lazily so the leads
        # app stays independent of clients' optional referral feature.
        if self.referring_client_id:
            try:
                from clients.referrals import credit_referrer

                credit_referrer(self)
            except Exception:
                pass
        # Seed the onboarding checklist so the new client gets the
        # standard "send welcome / kickoff / first invoice" punch-list.
        try:
            from clients.models import seed_onboarding_tasks

            seed_onboarding_tasks(client)
        except Exception:
            pass
        return client


class ActivityKind(models.TextChoices):
    NOTE = "note", "Note"
    CALL = "call", "Call"
    EMAIL = "email", "Email"
    MEETING = "meeting", "Meeting"
    QUOTE_SENT = "quote_sent", "Quote sent"
    STAGE_CHANGE = "stage_change", "Stage change"


class LeadActivity(models.Model):
    lead = models.ForeignKey(
        Lead, on_delete=models.CASCADE, related_name="activities"
    )
    kind = models.CharField(
        max_length=20, choices=ActivityKind.choices, default=ActivityKind.NOTE
    )
    body = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_activities",
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        indexes = [models.Index(fields=["lead", "-occurred_at"])]

    def __str__(self):
        return f"{self.get_kind_display()} on lead #{self.lead_id}"
