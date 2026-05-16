"""Fernet rotation: MultiFernet behaviour + rotate_fernet_keys command."""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.utils import timezone

from clients.encryption import _cipher, decrypt, encrypt, rotate
from clients.models import System

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_keys():
    """Return (new_key, old_key) as raw bytes for use with settings."""
    return Fernet.generate_key(), Fernet.generate_key()


# ----- module-level helpers --------------------------------------------


def test_encrypt_decrypt_roundtrip_single_key(settings, two_keys):
    new, _ = two_keys
    settings.FERNET_KEYS = new.decode()
    assert decrypt(encrypt("hello")) == "hello"


def test_decrypt_with_secondary_key(settings, two_keys):
    """A value encrypted under the old key should still decrypt after
    rotation (when the old key is still listed as secondary)."""
    new, old = two_keys

    settings.FERNET_KEYS = old.decode()
    ciphertext_old = encrypt("rotate me")

    settings.FERNET_KEYS = f"{new.decode()},{old.decode()}"
    assert decrypt(ciphertext_old) == "rotate me"


def test_rotate_moves_token_to_primary(settings, two_keys):
    new, old = two_keys

    settings.FERNET_KEYS = old.decode()
    ciphertext_old = encrypt("rotate me")

    settings.FERNET_KEYS = f"{new.decode()},{old.decode()}"
    rotated = rotate(ciphertext_old)
    assert rotated != ciphertext_old

    # Now only the new key — must still decrypt the rotated ciphertext.
    settings.FERNET_KEYS = new.decode()
    assert decrypt(rotated) == "rotate me"


def test_rotate_returns_empty_for_empty_input():
    assert rotate("") == ""


def test_decrypt_returns_empty_for_invalid_token(settings, two_keys):
    new, _ = two_keys
    settings.FERNET_KEYS = new.decode()
    assert decrypt("not-a-real-token") == ""


def test_legacy_fernet_key_fallback(settings, two_keys):
    """When FERNET_KEYS is empty FERNET_KEY is honoured."""
    new, _ = two_keys
    settings.FERNET_KEYS = ""
    settings.FERNET_KEY = new.decode()
    assert decrypt(encrypt("legacy")) == "legacy"


# ----- management command ----------------------------------------------


def test_rotate_fernet_keys_command_moves_db_rows(client_record, settings, two_keys):
    new, old = two_keys

    # Encrypt a System credential under the old key only.
    settings.FERNET_KEYS = old.decode()
    s = System.objects.create(client=client_record, type="network", name="UAP")
    s.set_credentials("admin:hunter2")
    s.save()
    old_cipher = s.credentials_encrypted

    # Prepend the new key, run the command, then drop the old key.
    settings.FERNET_KEYS = f"{new.decode()},{old.decode()}"
    out = StringIO()
    call_command("rotate_fernet_keys", stdout=out)

    s.refresh_from_db()
    assert s.credentials_encrypted != old_cipher

    settings.FERNET_KEYS = new.decode()
    s.refresh_from_db()
    assert s.get_credentials() == "admin:hunter2"


def test_rotate_fernet_keys_dry_run_does_not_persist(client_record, settings, two_keys):
    new, old = two_keys
    settings.FERNET_KEYS = old.decode()
    s = System.objects.create(client=client_record, type="network", name="UAP")
    s.set_credentials("admin:hunter2")
    s.save()
    before = s.credentials_encrypted

    settings.FERNET_KEYS = f"{new.decode()},{old.decode()}"
    out = StringIO()
    call_command("rotate_fernet_keys", "--dry-run", stdout=out)

    s.refresh_from_db()
    assert s.credentials_encrypted == before
    assert "Would re-encrypt 1" in out.getvalue()


def test_rotate_fernet_keys_handles_xero_connection(admin_user, settings, two_keys):
    """The same rotation pass covers XeroConnection.refresh_token_encrypted."""
    from billing.models import XeroConnection

    new, old = two_keys

    settings.FERNET_KEYS = old.decode()
    conn = XeroConnection(
        tenant_id="t",
        access_token="at",
        expires_at=timezone.now() + timedelta(hours=1),
        connected_by=admin_user,
    )
    conn.set_refresh_token("rt-secret")
    conn.save()

    settings.FERNET_KEYS = f"{new.decode()},{old.decode()}"
    call_command("rotate_fernet_keys", stdout=StringIO())

    settings.FERNET_KEYS = new.decode()
    conn.refresh_from_db()
    assert conn.get_refresh_token() == "rt-secret"
