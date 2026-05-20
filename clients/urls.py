from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ContactViewSet, SystemViewSet, my_referral_code

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("systems", SystemViewSet, basename="system")
router.register("contacts", ContactViewSet, basename="contact")

urlpatterns = [
    path("referral-code/", my_referral_code, name="my-referral-code"),
    *router.urls,
]
