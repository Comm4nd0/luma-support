from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import (
    Attachment,
    IngestEndpoint,
    MaintenanceSchedule,
    Ticket,
    TicketNote,
    TicketTag,
    TicketTemplate,
    TimeEntry,
)
from .serializers import (
    AttachmentSerializer,
    MaintenanceScheduleSerializer,
    TicketListSerializer,
    TicketNoteSerializer,
    TicketSerializer,
    TicketTagSerializer,
    TicketTemplateSerializer,
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

    def retrieve(self, request, *args, **kwargs):
        # Stamp the read-receipt when a client user opens the detail.
        # Staff opens don't move the marker — only clients viewing
        # signal "your reply has been seen".
        response = super().retrieve(request, *args, **kwargs)
        user = request.user
        if (
            user.is_authenticated
            and getattr(user, "is_client", False)
        ):
            from django.utils import timezone

            Ticket.objects.filter(pk=self.get_object().pk).update(
                client_last_viewed_at=timezone.now()
            )
        return response

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

    @action(detail=True, methods=["post"], url_path="merge-into/(?P<target_pk>[0-9]+)")
    def merge_into(self, request, pk=None, target_pk=None):
        """Move this ticket's notes / time entries / attachments / tags onto
        ``target_pk`` and close the source with a link back.

        Both tickets must belong to the same client — refusing cross-client
        merges is a guardrail against accidentally leaking notes between
        accounts.
        """
        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")

        from audit import log as audit_log

        source = self.get_object()
        try:
            target = Ticket.objects.get(pk=target_pk)
        except Ticket.DoesNotExist:
            raise ValidationError({"target": "no such ticket"})
        if source.pk == target.pk:
            raise ValidationError({"target": "cannot merge a ticket into itself"})
        if source.client_id != target.client_id:
            raise ValidationError(
                {"target": "merge target must belong to the same client"}
            )

        source.notes.update(ticket=target)
        source.time_entries.update(ticket=target)
        source.attachments.update(ticket=target)
        for tag in source.tags.all():
            target.tags.add(tag)

        from .models import TicketNote

        TicketNote.objects.create(
            ticket=target,
            author=request.user,
            body=f"Merged #{source.pk} ({source.subject}) into this ticket.",
            internal=True,
        )
        TicketNote.objects.create(
            ticket=source,
            author=request.user,
            body=f"Merged into #{target.pk}. Closing.",
            internal=True,
        )
        source.transition_to(Ticket.Status.CLOSED, by_user=request.user)

        audit_log(
            "ticket.merge",
            actor=request.user,
            request=request,
            target=source,
            merged_into=target.pk,
        )

        return Response(
            {
                "source": source.pk,
                "target": target.pk,
                "closed_source": True,
            }
        )

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request):
        """Apply one action to many tickets in one round-trip.

        Body: ``{"ids": [int, ...], "action": str, "value": <varies>}``.

        Actions:
            ``status``        -> value is one of Ticket.Status values.
            ``priority``      -> value is one of Ticket.Priority values.
            ``assigned_to``   -> value is a user id (or null to unassign).
            ``add_tag``       -> value is a tag id or slug.
            ``remove_tag``    -> value is a tag id or slug.

        Each touched ticket gets its own audit row so the trail is the
        same as the per-ticket equivalent action.
        """
        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")

        ids = request.data.get("ids") or []
        action_name = request.data.get("action")
        value = request.data.get("value")
        if not isinstance(ids, list) or not ids or not action_name:
            raise ValidationError({"detail": "ids and action are required."})

        from audit import log as audit_log

        qs = Ticket.objects.filter(pk__in=ids)
        tickets = list(qs)
        touched = 0
        for ticket in tickets:
            if action_name == "status":
                if value not in {v for v, _ in Ticket.Status.choices}:
                    raise ValidationError({"value": "invalid status"})
                ticket.transition_to(value, by_user=request.user)
            elif action_name == "priority":
                if value not in {v for v, _ in Ticket.Priority.choices}:
                    raise ValidationError({"value": "invalid priority"})
                ticket.priority = value
                ticket.save(update_fields=["priority"])
            elif action_name == "assigned_to":
                ticket.assigned_to_id = value
                ticket.save(update_fields=["assigned_to"])
            elif action_name in ("add_tag", "remove_tag"):
                tag = self._resolve_tag(value)
                if action_name == "add_tag":
                    ticket.tags.add(tag)
                else:
                    ticket.tags.remove(tag)
            else:
                raise ValidationError({"action": f"unknown action {action_name!r}"})
            audit_log(
                f"ticket.bulk.{action_name}",
                actor=request.user,
                request=request,
                target=ticket,
                value=value,
            )
            touched += 1
        return Response({"touched": touched})

    def _resolve_tag(self, value):
        if value is None:
            raise ValidationError({"value": "tag id or slug required"})
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            try:
                return TicketTag.objects.get(pk=int(value))
            except TicketTag.DoesNotExist:
                raise ValidationError({"value": "unknown tag id"})
        try:
            return TicketTag.objects.get(slug=value)
        except TicketTag.DoesNotExist:
            raise ValidationError({"value": "unknown tag slug"})

    @action(detail=False, methods=["get"], url_path="sla-analytics")
    def sla_analytics(self, request):
        """Staff-only: hit-rate per priority + worst clients over a window.

        Query params: ``days`` (default 30). Returns::

            {
              "window_days": 30,
              "totals": {"closed": N, "met": M, "breached": B, "hit_rate": 0.0..1.0},
              "by_priority": [
                {"priority": "high", "closed": N, "met": M, "hit_rate": ...},
                ...
              ],
              "worst_clients": [
                {"client_id": N, "name": "...", "closed": N, "breached": B},
                ...
              ]
            }
        """
        from datetime import timedelta

        from django.db.models import Count, F, Q
        from django.utils import timezone

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")

        try:
            days = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        since = timezone.now() - timedelta(days=days)

        # We only count tickets that actually closed in the window — open
        # ones aren't decided yet. A "met" close is one where resolved_at
        # was on or before the SLA deadline.
        closed_qs = Ticket.objects.filter(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED],
            resolved_at__gte=since,
            sla_deadline__isnull=False,
        )

        def _hit_rate(closed, met):
            return round(met / closed, 3) if closed else None

        totals = closed_qs.aggregate(
            closed=Count("id"),
            met=Count("id", filter=Q(resolved_at__lte=F("sla_deadline"))),
        )
        totals["breached"] = totals["closed"] - totals["met"]
        totals["hit_rate"] = _hit_rate(totals["closed"], totals["met"])

        by_priority = []
        for prio, _ in Ticket.Priority.choices:
            row = closed_qs.filter(priority=prio).aggregate(
                closed=Count("id"),
                met=Count("id", filter=Q(resolved_at__lte=F("sla_deadline"))),
            )
            if row["closed"]:
                row["breached"] = row["closed"] - row["met"]
                row["hit_rate"] = _hit_rate(row["closed"], row["met"])
                row["priority"] = prio
                by_priority.append(row)

        worst = (
            closed_qs.values("client_id", "client__name")
            .annotate(
                closed=Count("id"),
                breached=Count("id", filter=Q(resolved_at__gt=F("sla_deadline"))),
            )
            .filter(breached__gt=0)
            .order_by("-breached", "-closed")[:10]
        )
        worst_list = [
            {
                "client_id": r["client_id"],
                "name": r["client__name"],
                "closed": r["closed"],
                "breached": r["breached"],
            }
            for r in worst
        ]

        return Response(
            {
                "window_days": days,
                "totals": totals,
                "by_priority": by_priority,
                "worst_clients": worst_list,
            }
        )

    @action(detail=False, methods=["get"], url_path="sla-warnings")
    def sla_warnings(self, request):
        qs = Ticket.objects.sla_warnings()
        user = request.user
        if not user.can_view_all:
            qs = qs.filter(client_id=user.client_id) if user.client_id else qs.none()
        return Response(TicketListSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="summarise")
    def summarise(self, request, pk=None):
        """Staff-only: return a Claude TL;DR of the ticket thread.

        Cached on the ticket (``ai_summary`` / ``ai_summary_at``); the
        cache is invalidated by the TicketNote post_save signal so a
        stale summary never lingers after new conversation. Returns
        ``{"summary": ""}`` when ANTHROPIC_API_KEY is unset, mirroring
        ``draft_reply``.
        """
        from django.utils import timezone

        from .ai import summarise_thread

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")
        ticket = self.get_object()
        refresh = request.data.get("refresh") if hasattr(request, "data") else None
        if ticket.ai_summary and not refresh:
            return Response(
                {
                    "summary": ticket.ai_summary,
                    "generated_at": ticket.ai_summary_at,
                    "cached": True,
                }
            )
        summary = summarise_thread(ticket)
        if summary:
            Ticket.objects.filter(pk=ticket.pk).update(
                ai_summary=summary, ai_summary_at=timezone.now()
            )
            ticket.refresh_from_db(fields=["ai_summary", "ai_summary_at"])
        return Response(
            {
                "summary": summary,
                "generated_at": ticket.ai_summary_at,
                "cached": False,
            }
        )

    @action(detail=False, methods=["post"], url_path="inbox-zero")
    def inbox_zero(self, request):
        """Staff-only: Claude-suggested action per open ticket assigned to me.

        Body (optional): ``{"limit": int (default 15)}``. Returns
        ``{"suggestions": [{ticket_id, action, reason}, …]}``. Empty
        list when ANTHROPIC_API_KEY isn't set.
        """
        from .ai import propose_inbox_actions

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")
        try:
            limit = int(request.data.get("limit", 15))
        except (TypeError, ValueError):
            limit = 15
        limit = max(1, min(limit, 30))
        qs = (
            Ticket.objects.open()
            .filter(assigned_to=request.user)
            .order_by("sla_deadline", "-created_at")[:limit]
        )
        return Response({"suggestions": propose_inbox_actions(list(qs))})

    @action(detail=True, methods=["post"], url_path="promote-to-kb")
    def promote_to_kb(self, request, pk=None):
        """Staff-only: draft a KB article from this ticket via Claude.

        Returns ``{"draft": {"title", "content"}}`` (empty draft when
        ANTHROPIC_API_KEY isn't set). The caller is expected to review
        and POST to /api/v1/knowledge/articles/ to actually publish —
        we don't auto-create so a misfired AI suggestion never lands as
        a published article.
        """
        from .ai import draft_kb_article

        if not request.user.can_view_all:
            raise PermissionDenied("Staff only.")
        ticket = self.get_object()
        draft = draft_kb_article(ticket)
        return Response({"draft": draft})

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


class TicketTemplateViewSet(viewsets.ModelViewSet):
    """Staff-only CRUD for reusable canned replies."""

    queryset = TicketTemplate.objects.all()
    serializer_class = TicketTemplateSerializer
    ordering = ["name"]

    def get_queryset(self):
        if not self.request.user.can_view_all:
            return self.queryset.none()
        return super().get_queryset()

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

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


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
