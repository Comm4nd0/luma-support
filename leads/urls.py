from rest_framework.routers import DefaultRouter

from .views import LeadActivityViewSet, LeadViewSet

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("activities", LeadActivityViewSet, basename="lead-activity")

urlpatterns = router.urls
