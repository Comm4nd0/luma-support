from rest_framework.routers import DefaultRouter

from .views import TicketViewSet, TimeEntryViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("time-entries", TimeEntryViewSet, basename="timeentry")

urlpatterns = router.urls
