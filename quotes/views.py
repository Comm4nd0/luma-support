"""DRF API for quotes — staff-only."""
from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Quote
from .serializers import QuoteSerializer
from .services import accept_quote, reject_quote, send_quote


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "can_view_all", False))


class QuoteViewSet(viewsets.ModelViewSet):
    serializer_class = QuoteSerializer
    permission_classes = [IsStaff]
    filterset_fields = ["status", "client", "lead"]
    search_fields = ["number", "notes"]
    ordering_fields = ["created_at", "total", "valid_until"]

    def get_queryset(self):
        return (
            Quote.objects.select_related("client", "lead", "converted_invoice")
            .prefetch_related("lines")
            .all()
        )

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        quote = self.get_object()
        sent = send_quote(quote, by_user=request.user)
        return Response({"sent": sent, "quote": self.get_serializer(quote).data})

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        quote = self.get_object()
        reject_quote(
            quote,
            reason=request.data.get("reason", "") or "",
            by_user=request.user,
        )
        return Response(self.get_serializer(quote).data)

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        """Staff-facing accept (e.g. quote signed in person)."""
        quote = self.get_object()
        invoice = accept_quote(
            quote,
            accepted_by_name=request.data.get("accepted_by_name", "") or "",
        )
        return Response(
            {
                "invoice_id": invoice.pk,
                "quote": self.get_serializer(quote).data,
            }
        )
