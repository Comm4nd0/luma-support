"""Shared upload validation for user-supplied files.

Lives in the project package (rather than an app) because it is
cross-cutting infrastructure used by tickets, knowledge and clients —
the same way settings are shared — not a feature in its own right.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from rest_framework.serializers import ValidationError

# Extensions Marco actually exchanges with clients: images (incl. iPhone
# HEIC), documents, spreadsheets, logs, archives and short site videos.
# Executables, scripts and unknown types are rejected.
ALLOWED_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".heic",
    ".pdf",
    ".txt",
    ".csv",
    ".log",
    ".md",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".mp4",
    ".mov",
}


def validate_upload(f):
    """Validate an UploadedFile's size and extension.

    Raises DRF ``ValidationError`` (→ 400 response) so callers in views
    and serializers can use it directly.
    """
    max_bytes = getattr(settings, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)
    if f.size > max_bytes:
        raise ValidationError(
            f"File too large ({f.size} bytes); the limit is {max_bytes} bytes."
        )
    suffix = Path(f.name or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValidationError(
            f"File type '{suffix or '(none)'}' not allowed. Allowed: {allowed}."
        )
    return f
