"""Custom template context processors."""


def brand(request):
    """Brand colors / metadata exposed to every template."""
    return {
        "BRAND": {
            "name": "Luma Tech Solutions",
            "company": "Luma Tech Solutions",
            "url": "https://lumatechsolutions.co.uk",
            "primary": "#14b8a6",
            "primary_dark": "#0f766e",
            "background": "#0f172a",
            "surface": "#1e293b",
            "border": "#334155",
            "text": "#f1f5f9",
            "muted": "#94a3b8",
        }
    }


def unread_notifications(request):
    """Expose the current user's unread notification count to every template.

    Used by base.html to badge the Notifications nav link. Mirrors the
    mobile inbox unread indicator so the portal and the app stay in sync.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_notifications_count": 0}
    from notifications.models import Notification

    return {
        "unread_notifications_count": Notification.objects.filter(
            user=user, read=False
        ).count(),
    }
