"""Fernet rotation status snapshot."""
import pytest
from cryptography.fernet import Fernet

from clients.fernet_status import snapshot
from clients.models import System, SystemType

pytestmark = pytest.mark.django_db


def _multi(*keys: str, settings):
    settings.FERNET_KEYS = ",".join(keys)
    settings.FERNET_KEY = ""


def test_all_on_primary_when_one_key(settings, client_record):
    key = Fernet.generate_key().decode()
    _multi(key, settings=settings)
    s = System.objects.create(client=client_record, name="A", type=SystemType.NETWORK)
    s.set_credentials("secret")
    s.save()
    snap = snapshot()
    assert snap.total_with_creds == 1
    assert snap.on_primary == 1
    assert snap.on_old_key == 0
    assert snap.rotation_pct == 100
    assert snap.needs_rotation is False


def test_old_key_row_shows_as_needs_rotation(settings, client_record):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    # Encrypt under old key only.
    _multi(old, settings=settings)
    s = System.objects.create(client=client_record, name="A", type=SystemType.NETWORK)
    s.set_credentials("legacy")
    s.save()
    # Add a new primary key in front — old key still in the ring.
    _multi(new, old, settings=settings)
    snap = snapshot()
    assert snap.total_with_creds == 1
    assert snap.on_primary == 0
    assert snap.on_old_key == 1
    assert snap.rotation_pct == 0
    assert snap.needs_rotation is True


def test_no_credentials_is_full_completion(settings):
    _multi(Fernet.generate_key().decode(), settings=settings)
    snap = snapshot()
    assert snap.total_with_creds == 0
    assert snap.rotation_pct == 100
    assert snap.needs_rotation is False
