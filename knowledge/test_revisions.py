"""Tests for the ArticleRevision snapshotting signal."""
import pytest
from django.test import Client as DjangoClient

from knowledge.models import Article, ArticleRevision

pytestmark = pytest.mark.django_db


def test_create_records_initial_revision():
    a = Article.objects.create(title="UniFi setup", content="v1")
    assert ArticleRevision.objects.filter(article=a).count() == 1
    rev = a.revisions.first()
    assert rev.title == "UniFi setup"
    assert rev.content == "v1"


def test_content_edit_snapshots_previous_state():
    a = Article.objects.create(title="UniFi setup", content="v1")
    a.content = "v2 with more detail"
    a.save()
    revs = list(a.revisions.order_by("-edited_at"))
    assert len(revs) == 2
    # Newest first; the post-save snapshot captures the prior state.
    assert revs[0].content == "v1"
    assert revs[1].content == "v1"  # creation snapshot


def test_unrelated_field_change_does_not_make_a_revision():
    a = Article.objects.create(title="x", content="y", client_visible=False)
    a.client_visible = True
    a.save()
    # Still only the creation snapshot.
    assert a.revisions.count() == 1


def test_history_page_requires_staff(admin_user, client_record):
    from django.contrib.auth import get_user_model

    Article.objects.create(title="abc", content="x", slug="abc")
    User = get_user_model()
    cu = User.objects.create_user(
        email="cuh@acme.test", password="x", role=User.Role.CLIENT, client=client_record
    )
    web = DjangoClient()
    web.force_login(cu)
    resp = web.get("/kb/abc/history/")
    # StaffRequiredMixin redirects non-staff.
    assert resp.status_code in (302, 403)

    web.force_login(admin_user)
    resp = web.get("/kb/abc/history/")
    assert resp.status_code == 200
