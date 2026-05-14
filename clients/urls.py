from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ContactViewSet, SystemViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("systems", SystemViewSet, basename="system")
router.register("contacts", ContactViewSet, basename="contact")

urlpatterns = router.urls
