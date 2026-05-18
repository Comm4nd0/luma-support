"""DRF routes for the social API (mounted under /api/v1/social/)."""
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("accounts", views.SocialAccountViewSet, basename="social-account")
router.register("inbox", views.SocialInboxItemViewSet, basename="social-inbox")

urlpatterns = router.urls
