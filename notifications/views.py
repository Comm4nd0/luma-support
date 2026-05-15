from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    filterset_fields = ["type", "read"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.read = True
        notif.save(update_fields=["read"])
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({"status": "ok"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, read=False).count()
        return Response({"count": count})


class DeviceTokenViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Register / list / deactivate push-notification tokens.

    Create acts as an upsert keyed on token: a duplicate POST from the same
    user reactivates and re-binds without throwing UniqueConstraint. Tokens
    are also re-bound to the current user if another user previously owned
    them (a phone can change accounts).
    """

    serializer_class = DeviceTokenSerializer

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        defaults = {
            "user": request.user,
            "platform": serializer.validated_data["platform"],
            "app_version": serializer.validated_data.get("app_version", ""),
            "is_active": True,
        }
        obj, created = DeviceToken.objects.update_or_create(
            token=token, defaults=defaults
        )
        out = DeviceTokenSerializer(obj).data
        return Response(
            out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "last_seen_at"])
