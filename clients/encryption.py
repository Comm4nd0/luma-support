"""Fernet-based field encryption for credentials."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _cipher() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)


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
