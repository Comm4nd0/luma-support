import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        # Register the post_save signal that enqueues push fan-out.
        from . import signals  # noqa: F401

        # Initialise firebase-admin once, only when FCM is enabled and the
        # SDK is installed. Failures here are logged, not raised, so the
        # app still boots in dev/CI where Firebase isn't configured.
        if not getattr(settings, "FCM_ENABLED", False):
            return
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError:
            logger.warning("FCM_ENABLED=True but firebase-admin not installed")
            return

        if firebase_admin._apps:
            return

        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_JSON", "")
        try:
            cred = credentials.Certificate(cred_path) if cred_path else None
            firebase_admin.initialize_app(cred)
        except Exception as exc:  # noqa: BLE001
            logger.exception("firebase-admin init failed: %s", exc)
