from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, SystemViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("systems", SystemViewSet, basename="system")

urlpatterns = router.urls
