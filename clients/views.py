from rest_framework import viewsets

from .models import Client, System
from .serializers import ClientSerializer, SystemSerializer


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().prefetch_related("systems")
    serializer_class = ClientSerializer
    filterset_fields = ["care_plan_tier"]
    search_fields = ["name", "company", "email"]
    ordering_fields = ["name", "created_at", "care_plan_renewal"]


class SystemViewSet(viewsets.ModelViewSet):
    queryset = System.objects.select_related("client").all()
    serializer_class = SystemSerializer
    filterset_fields = ["type", "client"]
    search_fields = ["name", "description"]
