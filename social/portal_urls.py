"""Portal routes for OAuth + management (mounted under /portal/social/)."""
from django.urls import path

from . import views

urlpatterns = [
    path(
        "social/",
        views.SocialSettingsView.as_view(),
        name="social_settings",
    ),
    path(
        "social/inbox/",
        views.SocialInboxView.as_view(),
        name="social_inbox",
    ),
    path(
        "social/connect/<str:platform>/",
        views.SocialConnectView.as_view(),
        name="social_connect",
    ),
    path(
        "social/callback/<str:platform>/",
        views.SocialCallbackView.as_view(),
        name="social_callback",
    ),
    path(
        "social/<int:pk>/disconnect/",
        views.SocialDisconnectView.as_view(),
        name="social_disconnect",
    ),
]
