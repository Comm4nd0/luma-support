from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientViewSet,
    ContactViewSet,
    SiteVisitViewSet,
    SystemViewSet,
    my_referral_code,
    start_site_visit,
)

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("systems", SystemViewSet, basename="system")
router.register("contacts", ContactViewSet, basename="contact")
router.register("site-visits", SiteVisitViewSet, basename="sitevisit")

urlpatterns = [
    path("referral-code/", my_referral_code, name="my-referral-code"),
    path(
        "clients/<int:client_id>/site-visits/start/",
        start_site_visit,
        name="site-visit-start",
    ),
    *router.urls,
]
