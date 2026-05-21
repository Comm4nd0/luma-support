from rest_framework.routers import DefaultRouter

from .views import (
    MaintenanceScheduleViewSet,
    TicketTagViewSet,
    TicketTemplateViewSet,
    TicketViewSet,
    TimeEntryViewSet,
)

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("ticket-tags", TicketTagViewSet, basename="tickettag")
router.register("ticket-templates", TicketTemplateViewSet, basename="tickettemplate")
router.register("time-entries", TimeEntryViewSet, basename="timeentry")
router.register(
    "maintenance-schedules", MaintenanceScheduleViewSet, basename="maintenance"
)

urlpatterns = router.urls
