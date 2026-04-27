from django.urls import path

from .views import health, readyz

urlpatterns = [
    path("health/", health, name="health"),
    path("readyz/", readyz, name="readyz"),
]
