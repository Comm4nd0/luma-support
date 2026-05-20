from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Client, Contact, ReferralCode, System
from .serializers import (
    ClientSerializer,
    ContactSerializer,
    ReferralCodeSerializer,
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


class SystemViewSet(viewsets.ModelViewSet):
    queryset = System.objects.select_related("client").all()
    serializer_class = SystemSerializer
    filterset_fields = ["type", "client"]
    search_fields = ["name", "description"]

    def get_queryset(self):
        return _scope_to_user_client(super().get_queryset(), self.request.user)


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related("client").all()
    serializer_class = ContactSerializer
    filterset_fields = ["client", "is_primary"]
    search_fields = ["name", "email", "title"]

    def get_queryset(self):
        return _scope_to_user_client(super().get_queryset(), self.request.user)


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
