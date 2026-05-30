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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_setup(request):
    """POST /api/v1/auth/totp/setup/ — begin TOTP enrolment (mobile).

    Web parity for the portal's session-based TotpSetupView/TotpQrView.
    Generates a fresh secret, stores it encrypted (``totp_enabled`` stays
    False until confirmed) and returns the secret + otpauth provisioning
    URI so the app can render a QR / manual key. Refuses if TOTP is
    already enabled so an attacker with a live session can't silently
    rotate the second factor.
    """
    import pyotp

    user = request.user
    if user.totp_enabled:
        return Response({"detail": "totp_already_enabled"}, status=400)
    secret = pyotp.random_base32()
    user.set_totp_secret(secret)
    user.save(update_fields=["totp_secret_encrypted"])
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="Luma Tech Solutions"
    )
    return Response({"secret": secret, "otpauth_uri": uri})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def totp_confirm(request):
    """POST /api/v1/auth/totp/confirm/ — finish TOTP enrolment (mobile).

    Body ``{"code": "123456"}``. Verifies against the pending secret from
    ``totp_setup``; on success enables TOTP and returns a fresh set of
    recovery codes (shown once). Mirrors the portal's TotpVerifyView.
    """
    import pyotp

    from .models import RecoveryCode

    user = request.user
    if user.totp_enabled:
        return Response({"detail": "totp_already_enabled"}, status=400)
    secret = user.get_totp_secret()
    if not secret:
        return Response({"detail": "totp_not_started"}, status=400)
    code = (request.data.get("code") or "").strip().replace(" ", "")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return Response({"detail": "invalid_totp"}, status=400)
    user.totp_enabled = True
    user.save(update_fields=["totp_enabled"])
    codes = RecoveryCode.regenerate_for(user)
    return Response({"enabled": True, "recovery_codes": codes})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    """GET /api/v1/auth/sessions/ — outstanding (non-expired, non-blacklisted)
    refresh tokens for the current user."""
    from django.utils import timezone
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    blacklisted = set(
        BlacklistedToken.objects.values_list("token_id", flat=True)
    )
    now = timezone.now()
    rows = []
    qs = OutstandingToken.objects.filter(user=request.user).order_by("-created_at")
    for tok in qs:
        if tok.id in blacklisted or tok.expires_at < now:
            continue
        rows.append(
            {
                "id": tok.id,
                "jti": tok.jti,
                "created_at": tok.created_at,
                "expires_at": tok.expires_at,
            }
        )
    return Response({"sessions": rows})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_session(request, session_id: int):
    """POST /api/v1/auth/sessions/<id>/revoke/ — blacklist one refresh token."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    tok = OutstandingToken.objects.filter(
        pk=session_id, user=request.user
    ).first()
    if tok is None:
        return Response({"detail": "not found"}, status=404)
    BlacklistedToken.objects.get_or_create(token=tok)
    return Response({"revoked": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_all_sessions(request):
    """POST /api/v1/auth/sessions/revoke-all/ — blacklist every refresh
    token for the current user except (optionally) the one used to
    authenticate this call."""
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    qs = OutstandingToken.objects.filter(user=request.user)
    n = 0
    for tok in qs:
        _, created = BlacklistedToken.objects.get_or_create(token=tok)
        if created:
            n += 1
    return Response({"revoked": n})
