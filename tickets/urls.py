from django.urls import path
from rest_framework.routers import DefaultRouter

from .inbound_webhook import webhook_ingest
from .views import (
    MaintenanceScheduleViewSet,
    SavedTicketFilterViewSet,
    TicketTagViewSet,
    TicketTemplateViewSet,
    TicketViewSet,
    TimeEntryViewSet,
)

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("ticket-tags", TicketTagViewSet, basename="tickettag")
router.register("ticket-templates", TicketTemplateViewSet, basename="tickettemplate")
router.register(
    "saved-filters", SavedTicketFilterViewSet, basename="savedticketfilter"
)
router.register("time-entries", TimeEntryViewSet, basename="timeentry")
router.register(
    "maintenance-schedules", MaintenanceScheduleViewSet, basename="maintenance"
)

urlpatterns = router.urls + [
    path("webhook/<str:token>/", webhook_ingest, name="webhook-ingest"),
]
