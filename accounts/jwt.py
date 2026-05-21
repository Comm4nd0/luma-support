"""TOTP-aware JWT obtain view.

Overrides `rest_framework_simplejwt.views.TokenObtainPairView` so the
same endpoint that mobile clients (and djoser) already speak handles
the second factor:

  POST /api/v1/auth/jwt/create/
    Body: {"email": ..., "password": ..., "totp_code": ...}

Response codes:
  200 — tokens issued.
  401 with body {"detail": "totp_required"} — password OK, TOTP missing.
  401 with body {"detail": "invalid_totp"}  — password OK, TOTP wrong.
  401 (django default)                       — password wrong.

The portal flow is unchanged (it uses session login + the existing TOTP
verify view). Client-role users have no TOTP and skip the second factor.
"""
from __future__ import annotations

from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class _TotpRequiredError(exceptions.AuthenticationFailed):
    default_code = "totp_required"
    default_detail = "totp_required"


class _InvalidTotpError(exceptions.AuthenticationFailed):
    default_code = "invalid_totp"
    default_detail = "invalid_totp"


class TotpAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extends the standard pair serializer with an optional `totp_code`."""

    def validate(self, attrs):
        # Standard SimpleJWT validation: returns tokens dict on success and
        # binds `self.user`. Raises on bad password — let that bubble.
        data = super().validate(attrs)

        user = self.user
        if not getattr(user, "totp_enabled", False):
            return data

        code = (self.initial_data.get("totp_code") or "").strip().replace(" ", "")
        recovery = (self.initial_data.get("recovery_code") or "").strip()
        if not code and not recovery:
            raise _TotpRequiredError()

        # Recovery codes are a single-use fall-back when the phone is lost
        # — accepted in lieu of a TOTP code. Consumed on success.
        if recovery:
            from .models import RecoveryCode

            if RecoveryCode.consume(user, recovery):
                return data
            raise _InvalidTotpError()

        import pyotp

        secret = user.get_totp_secret()
        if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise _InvalidTotpError()
        return data


class TotpAwareTokenObtainPairView(TokenObtainPairView):
    serializer_class = TotpAwareTokenObtainPairSerializer


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def regenerate_recovery_codes(request):
    """POST /api/v1/auth/recovery-codes/ — refresh and return plaintext codes.

    Plaintext is shown once; the caller must present them to the user
    immediately and not store them.
    """
    from .models import RecoveryCode

    codes = RecoveryCode.regenerate_for(request.user)
    remaining = request.user.recovery_codes.filter(used_at__isnull=True).count()
    return Response({"codes": codes, "remaining": remaining})
