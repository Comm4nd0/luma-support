import pytest

from clients.encryption import decrypt, encrypt
from clients.models import Client, System, SystemType


@pytest.mark.django_db
def test_system_credentials_roundtrip(client_record):
    sys = System.objects.create(
        client=client_record, type=SystemType.NETWORK, name="UniFi"
    )
    sys.set_credentials("hunter2")
    sys.save()
    sys.refresh_from_db()
    assert sys.credentials_encrypted != "hunter2"  # actually encrypted
    assert sys.get_credentials() == "hunter2"


def test_encrypt_decrypt_empty():
    assert encrypt("") == ""
    assert decrypt("") == ""
