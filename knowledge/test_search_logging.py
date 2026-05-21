import pytest
from django.test import Client as DjangoClient
from rest_framework.test import APIClient

from knowledge.models import Article, KbSearchLog

pytestmark = pytest.mark.django_db


def test_api_search_logs_query(engineer_user):
    Article.objects.create(title="UniFi setup", content="...", published_at="2024-01-01T00:00:00Z")
    c = APIClient()
    c.force_authenticate(engineer_user)
    c.get("/api/v1/knowledge/articles/search/?q=unifi")
    log = KbSearchLog.objects.get()
    assert log.query == "unifi"
    assert log.results_count == 1
    assert log.source == "search"


def test_api_search_logs_zero_result(engineer_user):
    c = APIClient()
    c.force_authenticate(engineer_user)
    c.get("/api/v1/knowledge/articles/search/?q=nonexistent")
    log = KbSearchLog.objects.get()
    assert log.results_count == 0


def test_kb_gaps_report_lists_zero_result_queries(admin_user):
    KbSearchLog.objects.create(query="vpn", results_count=0)
    KbSearchLog.objects.create(query="vpn", results_count=0)
    KbSearchLog.objects.create(query="resolved", results_count=2)
    web = DjangoClient()
    web.force_login(admin_user)
    resp = web.get("/kb/gaps/")
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert "vpn" in body
    # Zero-result queries get a row; resolved query doesn't appear in the gaps table.
    assert body.count("<tr>") >= 2


def test_kb_gaps_report_requires_staff(client_record):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    cu = User.objects.create_user(
        email="c@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    web = DjangoClient()
    web.force_login(cu)
    resp = web.get("/kb/gaps/")
    # StaffRequiredMixin redirects authenticated non-staff to dashboard.
    assert resp.status_code in (302, 403)
