from decimal import Decimal

import pytest

from clients.encryption import decrypt, encrypt
from clients.models import Client, CustomerType, System, SystemType


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


@pytest.mark.django_db
def test_effective_billing_address_falls_back_to_address():
    c = Client.objects.create(name="A", address="123 Main St")
    assert c.effective_billing_address == "123 Main St"
    c.billing_address = "PO Box 9"
    assert c.effective_billing_address == "PO Box 9"


@pytest.mark.django_db
def test_effective_hourly_rate_uses_client_rate(settings):
    settings.DEFAULT_HOURLY_RATE = Decimal("75.00")
    c = Client.objects.create(name="B", hourly_rate=Decimal("90.00"))
    assert c.effective_hourly_rate() == Decimal("90.00")


@pytest.mark.django_db
def test_effective_hourly_rate_falls_back_to_settings(settings):
    settings.DEFAULT_HOURLY_RATE = Decimal("75.00")
    c = Client.objects.create(name="C")
    assert c.effective_hourly_rate() == Decimal("75.00")


@pytest.mark.django_db
def test_customer_type_defaults_to_home():
    c = Client.objects.create(name="D")
    assert c.customer_type == CustomerType.HOME
