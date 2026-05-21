from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import (
    Attachment,
    MaintenanceSchedule,
    Ticket,
    TicketNote,
    TicketTag,
    TimeEntry,
)
from .serializers import (
    AttachmentSerializer,
    MaintenanceScheduleSerializer,
    TicketListSerializer,
    TicketNoteSerializer,
    TicketSerializer,
    TicketTagSerializer,
    TimeEntrySerializer,
)


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.select_related(
        "client", "system", "assigned_to", "created_by"
    ).prefetch_related("time_entries", "attachments")

    filterset_fields = ["status", "priority", "client", "assigned_to", "system", "tags"]
    search_fields = ["subject", "description", "client__name"]
    ordering_fields = ["sla_deadline", "created_at", "priority"]
    ordering = ["sla_deadline", "-created_at"]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("tags")
        user = self.request.user
        if user.can_view_all:
            qs = self._maybe_filter_by_tag_slugs(qs)
            return qs
        if not user.client_id:
            return qs.none()
        return self._maybe_filter_by_tag_slugs(qs.filter(client_id=user.client_id))

    def _maybe_filter_by_tag_slugs(self, qs):
        """``?tag_slug=unifi&tag_slug=outage`` -> tickets with ALL slugs.

        Lets AI / inbound integrations filter without first resolving slugs
        to PKs.
        """
        slugs = self.request.query_params.getlist("tag_slug") if hasattr(
            self.request, "query_params"
        ) else []
        for slug in slugs:
            qs = qs.filter(tags__slug=slug)
        return qs.distinct() if slugs else qs

    def get_serializer_class(self):
        if self.action == "list":
            return TicketListSerializer
        return TicketSerializer

    def perform_create(self, serializer):
        user = self.request.user
        if not user.can_view_all:
            if not user.client_id:
                raise PermissionDenied("No client associated with your account.")
            serializer.save(created_by=user, client_id=user.client_id)
            return
        serializer.save(created_by=user)

    # --- custom actions ----------------------------------------------
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        ticket = self.get_object()
        new_status = request.data.get("status")
        valid = {value for value, _ in Ticket.Status.choices}
        if new_status not in valid:
            return Response({"detail": "Invalid status."}, status=400)
        ticket.transition_to(new_status, by_user=request.user)
        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="time")
    def log_time(self, request, pk=None):
        ticket = self.get_object()
        serializer = TimeEntrySerializer(data={**request.data, "ticket": ticket.pk})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, ticket=ticket)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def upload_attachment(self, request, pk=None):
        ticket = self.get_object()
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "Missing 'file' field."}, status=400)
        att = Attachment.objects.create(
            ticket=ticket, file=f, uploaded_by=request.user
        )
        return Response(
            AttachmentSerializer(att, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketNoteSerializer(data={**request.data, "ticket": ticket.pk})
        serializer.is_valid(raise_exception=True)
        note = serializer.save(author=request.user, ticket=ticket)
        self._notify_note(ticket, note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _notify_note(ticket, note):
        """Create a Notification for the counterparty when a non-internal
        note lands. The notifications signal turns this into a push."""
        if note.internal:
            return
        from notifications.models import Notification

        author = note.author
        recipients = set()
        # When a client posts, notify the engineer; when an engineer posts,
        # notify the client users tied to this ticket's client.
        if author is None or author.is_client:
            if ticket.assigned_to and ticket.assigned_to_id != getattr(author, "pk", None):
                recipients.add(ticket.assigned_to)
        else:
            for u in ticket.client.users.filter(is_active=True):
                if u.pk != getattr(author, "pk", None):
                    recipients.add(u)

        for user in recipients:
            Notification.objects.create(
                user=user,
                type=Notification.Type.TICKET_UPDATE,
                title=f"New note on #{ticket.pk}",
                body=note.body[:240],
                related_ticket=ticket,
            )

    @action(detail=False, methods=["get"], url_path="sla-warnings")
    def sla_warnings(self, request):
        qs = Ticket.objects.sla_warnings()
        user = request.user
        if not user.can_view_all:
            qs = qs.filter(client_id=user.client_id) if user.client_id else qs.none()
        return Response(TicketListSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="draft-reply")
    def draft_reply(self, request, pk=None):
        """Staff-only: ask Claude for an engineer-side draft reply.

        Returns `{"draft": "..."}` — empty when ANTHROPIC_API_KEY is
        unset or the call fails, so mobile / portal can decide whether
        to surface the button.
        """
        from .ai import draft_reply as _draft

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")
        ticket = self.get_object()
        return Response({"draft": _draft(ticket)})

    @action(detail=False, methods=["get"], url_path="dashboard-stats")
    def dashboard_stats(self, request):
        """Staff-only KPI bundle for the mobile engineer dashboard.

        Mirrors the cards on the portal dashboard so both front-ends
        render identical numbers from a single round-trip.
        """
        from datetime import timedelta
        from decimal import Decimal

        from django.conf import settings as dj_settings
        from django.db.models import Sum
        from django.utils import timezone

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")

        from billing.models import Invoice, Payment

        from .models import MaintenanceSchedule

        now = timezone.now()
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        unbilled_minutes = (
            TimeEntry.objects.filter(billable=True, invoice_line__isnull=True)
            .aggregate(total=Sum("minutes"))["total"]
            or 0
        )
        mtd_invoiced = (
            Invoice.objects.filter(created_at__gte=month_start)
            .aggregate(total=Sum("total"))["total"]
            or Decimal("0")
        )
        mtd_paid = (
            Payment.objects.filter(paid_at__gte=month_start)
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        overdue = Invoice.objects.filter(
            status__in=[Invoice.Status.SENT, Invoice.Status.AUTHORISED],
            due_date__lt=timezone.localdate(),
        ).count()
        maintenance_due = MaintenanceSchedule.objects.filter(
            active=True,
            next_run_at__lte=timezone.localdate() + timedelta(days=7),
        ).count()

        # Social accounts roll-up — kept inline (rather than its own
        # endpoint) so the mobile dashboard hydrates in one round trip.
        from social.models import InboxStatus, SocialAccount, SocialInboxItem

        social_accounts = [
            {
                "id": a.pk,
                "platform": a.platform,
                "platform_display": a.get_platform_display(),
                "display_name": a.display_name,
                "health_status": a.health_status,
                "followers": a.followers,
                "followers_delta_7d": a.followers_delta_7d,
                "days_since_last_post": a.days_since_last_post,
                "last_error": a.last_error,
            }
            for a in SocialAccount.objects.all()
        ]
        social_inbox_unread = SocialInboxItem.objects.filter(
            status=InboxStatus.OPEN
        ).count()

        return Response(
            {
                "unbilled_hours": float(
                    Decimal(unbilled_minutes) / Decimal(60)
                ),
                "mtd_invoiced": str(mtd_invoiced),
                "mtd_paid": str(mtd_paid),
                "overdue_invoices": overdue,
                "maintenance_due_7d": maintenance_due,
                "currency": getattr(dj_settings, "DEFAULT_CURRENCY", "GBP"),
                "social_accounts": social_accounts,
                "social_inbox_unread": social_inbox_unread,
            }
        )


class MaintenanceScheduleViewSet(viewsets.ModelViewSet):
    """Staff-only CRUD for the recurring-ticket templates."""

    queryset = MaintenanceSchedule.objects.select_related(
        "client", "system", "default_assignee"
    )
    serializer_class = MaintenanceScheduleSerializer
    filterset_fields = ["client", "cadence", "active"]
    ordering_fields = ["next_run_at", "created_at"]
    ordering = ["next_run_at", "id"]

    def get_queryset(self):
        if not self.request.user.can_view_all:
            return self.queryset.none()
        return super().get_queryset()


class TicketTagViewSet(viewsets.ModelViewSet):
    """CRUD for ticket tags. Read open to any authenticated user;
    write restricted to staff so clients can't pollute the taxonomy."""

    queryset = TicketTag.objects.all()
    serializer_class = TicketTagSerializer
    ordering = ["name"]

    def get_permissions(self):
        # Default permissions (IsAuthenticated) apply for read.
        return super().get_permissions()

    def _require_staff(self):
        if not self.request.user.can_view_all:
            raise PermissionDenied("Staff only.")

    def create(self, request, *args, **kwargs):
        self._require_staff()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._require_staff()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._require_staff()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._require_staff()
        return super().destroy(request, *args, **kwargs)


class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.select_related("ticket", "user").all()
    serializer_class = TimeEntrySerializer
    filterset_fields = ["ticket", "user", "billable"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.can_view_all:
            return qs
        return (
            qs.filter(ticket__client_id=user.client_id)
            if user.client_id
            else qs.none()
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
