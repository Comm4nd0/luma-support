from rest_framework import viewsets

from .models import User
from .serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """User account management.

    Staff (admin/engineer) and Django superusers see every user. Client
    users only see themselves and any other users tied to their client.
    Write operations remain gated on staff/superuser status.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ["role", "is_active", "client"]
    search_fields = ["email", "first_name", "last_name"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.can_view_all:
            return qs
        if user.client_id:
            return qs.filter(client_id=user.client_id)
        return qs.filter(pk=user.pk)

    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser, IsAuthenticated

        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdminUser()]
