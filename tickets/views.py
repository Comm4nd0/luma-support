from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Attachment, Ticket, TicketNote, TimeEntry
from .serializers import (
    AttachmentSerializer,
    TicketListSerializer,
    TicketNoteSerializer,
    TicketSerializer,
    TimeEntrySerializer,
)


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.select_related(
        "client", "system", "assigned_to", "created_by"
    ).prefetch_related("time_entries", "attachments")

    filterset_fields = ["status", "priority", "client", "assigned_to", "system"]
    search_fields = ["subject", "description", "client__name"]
    ordering_fields = ["sla_deadline", "created_at", "priority"]
    ordering = ["sla_deadline", "-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return TicketListSerializer
        return TicketSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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
        serializer.save(author=request.user, ticket=ticket)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="sla-warnings")
    def sla_warnings(self, request):
        qs = Ticket.objects.sla_warnings()
        return Response(TicketListSerializer(qs, many=True).data)


class TimeEntryViewSet(viewsets.ModelViewSet):
    queryset = TimeEntry.objects.select_related("ticket", "user").all()
    serializer_class = TimeEntrySerializer
    filterset_fields = ["ticket", "user", "billable"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
