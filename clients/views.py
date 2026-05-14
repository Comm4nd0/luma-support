from rest_framework import viewsets

from .models import Client, Contact, System
from .serializers import ClientSerializer, ContactSerializer, SystemSerializer


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
