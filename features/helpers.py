"""Tiny helper around FeatureFlag — never raises, returns False on error."""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def is_enabled(name: str, *, user: Optional[Any] = None) -> bool:
    """Return True when feature ``name`` is on for ``user``.

    - Missing row -> False (features default off).
    - ``allowed_users`` non-empty -> only those users (overrides percentage).
    - ``percentage`` -> deterministic per-user bucket (modulo 100 of a
      stable hash) so a given user's "in/out" state is consistent across
      requests for a given percentage.
    - No user -> treated as anonymous (bucket 0): in iff percentage > 0.
    """
    try:
        from .models import FeatureFlag

        flag = FeatureFlag.objects.filter(name=name).first()
        if flag is None or not flag.enabled:
            return False
        user_id = getattr(user, "pk", None) if user is not None else None
        if flag.allowed_users.exists():
            if user_id is None:
                return False
            return flag.allowed_users.filter(pk=user_id).exists()
        if flag.percentage >= 100:
            return True
        if flag.percentage <= 0:
            return False
        bucket = _bucket(f"{name}:{user_id or 0}")
        return bucket < flag.percentage
    except Exception:
        logger.exception("features.is_enabled failed for %s", name)
        return False


def _bucket(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 100
