import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_engineer_redirected_from_invoice_list(client, engineer_user):
    client.force_login(engineer_user)
    resp = client.get(reverse("portal:invoice_list"))
    assert resp.status_code == 302
    assert resp.url == reverse("portal:dashboard")


@pytest.mark.django_db
def test_anonymous_redirected_to_login(client):
    resp = client.get(reverse("portal:invoice_list"))
    assert resp.status_code == 302
    assert "/login" in resp.url


@pytest.mark.django_db
def test_admin_can_view_invoice_list(client, admin_user):
    client.force_login(admin_user)
    resp = client.get(reverse("portal:invoice_list"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_admin_can_view_xero_settings(client, admin_user):
    client.force_login(admin_user)
    resp = client.get(reverse("portal:xero_settings"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_engineer_cannot_generate_time_invoice(client, engineer_user, client_record):
    client.force_login(engineer_user)
    resp = client.post(
        reverse("portal:client_generate_time_invoice", args=[client_record.pk])
    )
    assert resp.status_code == 302
    assert resp.url == reverse("portal:dashboard")
