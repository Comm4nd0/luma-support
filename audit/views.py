from rest_framework import mixins, permissions, viewsets

from .models import AuditLog
from .serializers import AuditLogSerializer


class IsAdminRole(permissions.BasePermission):
    """Only admins can read the audit log. Engineers don't."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_admin_role", False)
        )


class AuditLogViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Read-only audit log feed for admin users."""

    queryset = AuditLog.objects.select_related("actor", "target_ct")
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    filterset_fields = ["actor", "action"]
    search_fields = ["action", "target_repr", "actor__email", "ip"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
