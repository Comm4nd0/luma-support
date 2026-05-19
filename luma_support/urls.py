"""URL configuration for luma_support project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.jwt import TotpAwareTokenObtainPairView

api_v1 = [
    # TOTP-aware token endpoint must come BEFORE djoser.urls.jwt so it
    # shadows djoser's plain TokenObtainPairView at the same path.
    path("auth/jwt/create/", TotpAwareTokenObtainPairView.as_view()),
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.jwt")),
    path("accounts/", include("accounts.urls")),
    path("audit/", include("audit.urls")),
    path("billing/", include("billing.urls")),
    path("clients/", include("clients.urls")),
    path("tickets/", include("tickets.urls")),
    path("knowledge/", include("knowledge.urls")),
    path("notifications/", include("notifications.urls")),
    path("social/", include("social.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "api"), namespace="v1")),
    path("system/", include("system.urls")),
    path("", include("luma_support.portal_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
