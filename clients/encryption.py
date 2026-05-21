"""Fernet-based field encryption with key rotation support.

Supports either FERNET_KEY (single key — legacy) or FERNET_KEYS
(comma-separated, primary first). Writes always use the primary key;
reads try each key in order so retiring an old key just means dropping
it from the list after `manage.py rotate_fernet_keys` has re-encrypted
every existing ciphertext.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings


def _keys() -> list[bytes]:
    """Active Fernet keys, primary first."""
    raw = getattr(settings, "FERNET_KEYS", "") or ""
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        items = [k.strip() for k in str(raw).split(",") if k.strip()]
    if not items:
        single = getattr(settings, "FERNET_KEY", "")
        if single:
            items = [single]
    return [k.encode() if isinstance(k, str) else k for k in items]


def _cipher() -> MultiFernet:
    keys = _keys()
    if not keys:
        raise RuntimeError("No FERNET_KEY(S) configured")
    return MultiFernet([Fernet(k) for k in keys])


def encrypt(value: str) -> str:
    if not value:
        return ""
    return _cipher().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _cipher().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def rotate(token: str) -> str:
    """Re-encrypt `token` so it lands under the current primary key.

    Returns the input unchanged if it's empty or undecryptable, so a
    corrupted row doesn't break the rotation command.
    """
    if not token:
        return token
    try:
        return _cipher().rotate(token.encode()).decode()
    except InvalidToken:
        return token


def encrypted_with_primary(token: str) -> bool | None:
    """True iff ``token`` decrypts under the primary (first) key only.

    Returns None for empty input or undecryptable rows. Used by the
    Fernet rotation status report to show how many credential blobs
    still need rotating.
    """
    if not token:
        return None
    keys = _keys()
    if not keys:
        return None
    try:
        Fernet(keys[0]).decrypt(token.encode())
        return True
    except InvalidToken:
        # Decryptable by some other key in the ring, but not the primary.
        try:
            _cipher().decrypt(token.encode())
            return False
        except InvalidToken:
            return None
