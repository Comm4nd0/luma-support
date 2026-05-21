from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "client",
            "is_staff",
            "is_active",
            "date_joined",
            "quiet_hours_start",
            "quiet_hours_end",
            "quiet_hours_critical_override",
        )
        read_only_fields = ("id", "is_staff", "date_joined")


class UserCreateSerializer(BaseUserCreateSerializer):
    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = (
            "id",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
            "phone",
            "client",
        )
