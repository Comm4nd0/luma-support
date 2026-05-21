from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Client, Contact, ReferralCode, SiteVisit, System
from .serializers import (
    ClientSerializer,
    ContactSerializer,
    ReferralCodeSerializer,
    SiteVisitSerializer,
    SystemSerializer,
)


def _scope_to_user_client(qs, user, client_field: str = "client_id"):
    """Return `qs` unchanged for staff/superusers; otherwise filter to the
    user's own client. Users without an associated client see nothing."""
    if user.can_view_all:
        return qs
    if not user.client_id:
        return qs.none()
    return qs.filter(**{client_field: user.client_id})


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().prefetch_related("systems", "contacts")
    serializer_class = ClientSerializer
    filterset_fields = ["care_plan_tier"]
    search_fields = ["name", "company", "email"]
    ordering_fields = ["name", "created_at", "care_plan_renewal"]

    def get_queryset(self):
        return _scope_to_user_client(super().get_queryset(), self.request.user, "id")

    @action(detail=True, methods=["get"])
    def health(self, request, pk=None):
        """Return the per-component health score breakdown.

        Same shape that the portal's expandable health panel renders —
        score, band, CSAT avg, open ticket count, overdue invoices,
        systems %, and a list of human reasons.
        """
        from .health import score_client

        client = self.get_object()
        snapshot = score_client(client)
        return Response(
            {
                "client_id": snapshot.client_id,
                "score": snapshot.score,
                "band": snapshot.band,
                "csat": snapshot.csat,
                "open_tickets": snapshot.open_tickets,
                "overdue_invoices": snapshot.overdue_invoices,
                "systems_ok_pct": snapshot.systems_ok_pct,
                "reasons": snapshot.reasons,
            }
        )


class SystemViewSet(viewsets.ModelViewSet):
    queryset = System.objects.select_related("client").all()
    serializer_class = SystemSerializer
    filterset_fields = ["type", "client"]
    search_fields = ["name", "description"]

    def get_queryset(self):
        return _scope_to_user_client(super().get_queryset(), self.request.user)

    @action(detail=True, methods=["post"], url_path="request-credential-rotation")
    def request_credential_rotation(self, request, pk=None):
        """Client-facing: open a ticket asking us to rotate stored creds.

        Lets a client say "please change the UniFi admin password" without
        ever needing to see the current one.
        """
        from tickets.models import Ticket

        system = self.get_object()
        ticket = Ticket.objects.create(
            client=system.client,
            system=system,
            subject=f"Please rotate credentials for {system.name}",
            description=(
                f"{request.user.email if request.user.is_authenticated else 'A client'} "
                f"requested credential rotation for system "
                f"#{system.pk} ({system.name})."
            ),
            priority="medium",
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(
            {"ticket_id": ticket.pk}, status=status.HTTP_201_CREATED
        )


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related("client").all()
    serializer_class = ContactSerializer
    filterset_fields = ["client", "is_primary"]
    search_fields = ["name", "email", "title"]

    def get_queryset(self):
        return _scope_to_user_client(super().get_queryset(), self.request.user)


class SiteVisitViewSet(viewsets.ModelViewSet):
    """Staff-only site-visit logbook.

    The lifecycle is two endpoints rather than CRUD-style writes:
    POST /clients/<id>/site-visits/start/ opens a visit (with optional
    lat/lon), and POST /site-visits/<id>/end/ closes it, stamping
    ended_at + creating a billable TimeEntry on whichever ticket the
    caller passes (so the visit time lands in the existing
    time-tracking analytics).
    """

    queryset = SiteVisit.objects.select_related("client", "user").all()
    serializer_class = SiteVisitSerializer
    filterset_fields = ["client", "user"]

    def get_queryset(self):
        if not self.request.user.can_view_all:
            return self.queryset.none()
        return super().get_queryset()

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        """Close an open visit; optionally roll it into a TimeEntry."""
        from django.utils import timezone

        from audit import log as audit_log
        from tickets.models import Ticket, TimeEntry

        visit = self.get_object()
        if visit.ended_at is not None:
            return Response({"detail": "already ended"}, status=400)
        if visit.user_id != request.user.pk and not request.user.is_admin_role:
            return Response({"detail": "not your visit"}, status=403)

        visit.ended_at = timezone.now()
        lat = request.data.get("lat")
        lon = request.data.get("lon")
        if lat is not None:
            visit.lat_end = lat
        if lon is not None:
            visit.lon_end = lon
        notes = (request.data.get("notes") or "").strip()
        if notes:
            visit.notes = (visit.notes + ("\n" if visit.notes else "") + notes)
        # Optional: bill this visit's minutes against a ticket.
        ticket_id = request.data.get("ticket")
        if ticket_id and visit.duration_minutes:
            ticket = Ticket.objects.filter(
                pk=int(ticket_id), client=visit.client
            ).first()
            if ticket is None:
                return Response(
                    {"detail": "ticket not found or wrong client"}, status=400
                )
            visit.time_entry = TimeEntry.objects.create(
                ticket=ticket, user=visit.user,
                minutes=visit.duration_minutes,
                description=f"Site visit at {visit.client.name}",
                billable=True,
            )
        visit.save()
        audit_log(
            "site_visit.end",
            actor=request.user,
            request=request,
            target=visit.client,
            visit_id=visit.pk,
            minutes=visit.duration_minutes,
        )
        return Response(self.get_serializer(visit).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_site_visit(request, client_id: int):
    """POST /api/v1/clients/clients/<id>/site-visits/start/ — open a visit."""
    from audit import log as audit_log

    if not request.user.can_view_all:
        return Response({"detail": "Staff only."}, status=403)
    client = Client.objects.filter(pk=client_id).first()
    if client is None:
        return Response({"detail": "client not found"}, status=404)
    visit = SiteVisit.objects.create(
        client=client,
        user=request.user,
        lat_start=request.data.get("lat"),
        lon_start=request.data.get("lon"),
    )
    audit_log(
        "site_visit.start",
        actor=request.user,
        request=request,
        target=client,
        visit_id=visit.pk,
        lat=str(visit.lat_start) if visit.lat_start else "",
        lon=str(visit.lon_start) if visit.lon_start else "",
    )
    return Response(SiteVisitSerializer(visit).data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_referral_code(request):
    """Return the requesting user's client's referral code + stats."""
    user = request.user
    client = getattr(user, "client", None)
    if client is None:
        return Response(
            {"detail": "Account not linked to a client."},
            status=status.HTTP_404_NOT_FOUND,
        )
    code = ReferralCode.for_client(client)
    share_link = request.build_absolute_uri(f"/r/{code.code}/")
    data = ReferralCodeSerializer(code).data
    data["share_link"] = share_link
    return Response(data)
