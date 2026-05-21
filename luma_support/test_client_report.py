import pytest
from django.test import Client as DjangoClient

pytestmark = pytest.mark.django_db


def test_monthly_report_pdf_downloads_for_admin(admin_user, client_record):
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get(f"/clients/{client_record.pk}/report.pdf?year=2026&month=1")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    # ReportLab PDFs always start with %PDF.
    assert resp.content[:4] == b"%PDF"
    assert "attachment" in resp["Content-Disposition"]
    assert f"luma-report-{client_record.pk}-2026-01.pdf" in resp["Content-Disposition"]


def test_monthly_report_rejects_client_users(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="r@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    web = DjangoClient()
    web.force_login(cu)
    resp = web.get(f"/clients/{client_record.pk}/report.pdf")
    # StaffRequiredMixin redirects authenticated non-staff to dashboard.
    assert resp.status_code in (302, 403)


def test_monthly_report_validates_month(admin_user, client_record):
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get(f"/clients/{client_record.pk}/report.pdf?year=2026&month=13")
    # Out-of-range month redirects with a flash error.
    assert resp.status_code in (302,)
