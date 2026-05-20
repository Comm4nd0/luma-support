"""DRF API for leads.

Staff-only (engineer + admin). The pipeline is internal — client users
never see it. Public lead-capture is a separate, unauthenticated view
in `leads.public` (Phase A4).
"""
from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from audit import log as audit_log

from .models import ActivityKind, Lead, LeadActivity, LeadStage
from .serializers import LeadActivitySerializer, LeadSerializer


class IsStaff(permissions.BasePermission):
    """Engineer + admin only. Clients never touch the pipeline."""

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "can_view_all", False))


class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [IsStaff]
    filterset_fields = ["stage", "source", "assigned_to", "customer_type"]
    search_fields = ["name", "email", "company", "interest"]
    ordering_fields = [
        "created_at",
        "next_action_at",
        "estimated_value",
        "stage",
    ]

    def get_queryset(self):
        return (
            Lead.objects.select_related(
                "assigned_to", "referring_client", "converted_client"
            )
            .prefetch_related("activities__actor")
            .all()
        )

    def perform_create(self, serializer):
        lead = serializer.save()
        audit_log("lead.create", request=self.request, target=lead)

    def perform_update(self, serializer):
        # Detect stage changes so we can write a STAGE_CHANGE activity.
        prior_stage = Lead.objects.values_list("stage", flat=True).get(
            pk=serializer.instance.pk
        )
        lead = serializer.save()
        if prior_stage != lead.stage:
            LeadActivity.objects.create(
                lead=lead,
                kind=ActivityKind.STAGE_CHANGE,
                body=f"{prior_stage} → {lead.stage}",
                actor=self.request.user,
            )
            audit_log(
                "lead.stage_change",
                request=self.request,
                target=lead,
                from_stage=prior_stage,
                to_stage=lead.stage,
            )

    @action(detail=True, methods=["post"], url_path="advance")
    def advance(self, request, pk=None):
        """Move a lead to a new stage.

        Body: `{"stage": "qualified", "lost_reason": "optional"}`.
        """
        lead = self.get_object()
        new_stage = request.data.get("stage")
        valid = {value for value, _ in LeadStage.choices}
        if new_stage not in valid:
            return Response(
                {"detail": "Invalid stage."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lead.transition_to(
            new_stage,
            by_user=request.user,
            lost_reason=request.data.get("lost_reason", "") or "",
        )
        audit_log(
            "lead.stage_change",
            request=request,
            target=lead,
            to_stage=new_stage,
        )
        return Response(self.get_serializer(lead).data)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        """Convert a Lead into a Client (and link the two records)."""
        lead = self.get_object()
        client = lead.convert_to_client(by_user=request.user)
        audit_log(
            "lead.convert",
            request=request,
            target=lead,
            client_id=client.pk,
        )
        return Response(
            {
                "lead": self.get_serializer(lead).data,
                "client_id": client.pk,
            }
        )

    @action(detail=True, methods=["post"], url_path="activities")
    def add_activity(self, request, pk=None):
        """Append a new LeadActivity (call, email, note, ...) to a lead."""
        lead = self.get_object()
        kind = request.data.get("kind") or ActivityKind.NOTE
        valid = {value for value, _ in ActivityKind.choices}
        if kind not in valid:
            return Response(
                {"detail": "Invalid activity kind."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response(
                {"detail": "Body cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        activity = LeadActivity.objects.create(
            lead=lead,
            kind=kind,
            body=body,
            actor=request.user,
        )
        return Response(
            LeadActivitySerializer(activity).data,
            status=status.HTTP_201_CREATED,
        )


class LeadActivityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeadActivitySerializer
    permission_classes = [IsStaff]
    filterset_fields = ["lead", "kind", "actor"]

    def get_queryset(self):
        return LeadActivity.objects.select_related("actor", "lead").all()
