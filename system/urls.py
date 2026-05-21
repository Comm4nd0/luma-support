from django.urls import path

from .views import health, integrations, readyz

urlpatterns = [
    path("health/", health, name="health"),
    path("readyz/", readyz, name="readyz"),
    path("integrations/", integrations, name="integrations"),
]
