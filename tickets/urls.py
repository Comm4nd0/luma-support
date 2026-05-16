from rest_framework.routers import DefaultRouter

from .views import MaintenanceScheduleViewSet, TicketViewSet, TimeEntryViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("time-entries", TimeEntryViewSet, basename="timeentry")
router.register(
    "maintenance-schedules", MaintenanceScheduleViewSet, basename="maintenance"
)

urlpatterns = router.urls
