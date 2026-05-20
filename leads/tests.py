from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from clients.models import Client
from notifications.models import Notification

from .models import ActivityKind, Lead, LeadActivity, LeadSource, LeadStage


# -----------------------------------------------------------------
# Model behaviour
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_lead_defaults():
    lead = Lead.objects.create(name="Alice", email="a@example.com")
    assert lead.stage == LeadStage.NEW
    assert lead.source == LeadSource.OTHER
    assert lead.is_active
    assert not lead.is_overdue


@pytest.mark.django_db
def test_is_overdue_only_when_active_and_past_due():
    past = timezone.now() - timedelta(hours=1)
    lead = Lead.objects.create(name="Bob", next_action_at=past)
    assert lead.is_overdue is True

    lead.stage = LeadStage.WON
    lead.save()
    assert lead.is_overdue is False


@pytest.mark.django_db
def test_transition_to_logs_stage_change(engineer_user):
    lead = Lead.objects.create(name="Carla")
    lead.transition_to(LeadStage.CONTACTED, by_user=engineer_user)
    lead.refresh_from_db()
    assert lead.stage == LeadStage.CONTACTED
    activity = lead.activities.first()
    assert activity.kind == ActivityKind.STAGE_CHANGE
    assert activity.actor == engineer_user


@pytest.mark.django_db
def test_transition_to_records_lost_reason():
    lead = Lead.objects.create(name="Dan")
    lead.transition_to(LeadStage.LOST, lost_reason="too expensive")
    lead.refresh_from_db()
    assert lead.stage == LeadStage.LOST
    assert lead.lost_reason == "too expensive"
    assert "too expensive" in lead.activities.first().body


@pytest.mark.django_db
def test_convert_to_client_creates_client_and_links_back(engineer_user):
    lead = Lead.objects.create(
        name="Erin",
        company="Erin Ltd",
        email="erin@example.com",
        phone="07000 000000",
        customer_type="business",
        interest="UniFi install",
    )
    client = lead.convert_to_client(by_user=engineer_user)
    lead.refresh_from_db()

    assert client.pk is not None
    assert client.name == "Erin"
    assert client.email == "erin@example.com"
    assert client.customer_type == "business"
    assert lead.stage == LeadStage.WON
    assert lead.converted_client_id == client.pk
    assert lead.converted_at is not None
    # Activity log records the conversion.
    assert any(
        "client #" in a.body for a in lead.activities.all()
    )


@pytest.mark.django_db
def test_convert_is_idempotent(engineer_user):
    lead = Lead.objects.create(name="Finn")
    first = lead.convert_to_client(by_user=engineer_user)
    again = lead.convert_to_client(by_user=engineer_user)
    assert first.pk == again.pk
    # Only one client was created for this lead.
    assert Client.objects.filter(origin_leads=lead).count() == 1


# -----------------------------------------------------------------
# Portal
# -----------------------------------------------------------------


@pytest.fixture
def auth_client(client, engineer_user):
    """A logged-in Django test client (engineer role) with 2FA bypassed."""
    engineer_user.totp_enabled = True
    engineer_user.set_totp_secret("JBSWY3DPEHPK3PXP")
    engineer_user.save()
    client.force_login(engineer_user)
    return client


@pytest.mark.django_db
def test_portal_list_renders(auth_client):
    Lead.objects.create(name="Grace", stage=LeadStage.NEW)
    Lead.objects.create(name="Henry", stage=LeadStage.QUOTED)
    resp = auth_client.get(reverse("portal:lead_list"))
    assert resp.status_code == 200
    assert b"Grace" in resp.content
    assert b"Henry" in resp.content


@pytest.mark.django_db
def test_portal_create_lead(auth_client):
    resp = auth_client.post(
        reverse("portal:lead_create"),
        data={
            "name": "Ivy",
            "company": "Ivy Co",
            "email": "ivy@example.com",
            "phone": "",
            "customer_type": "home",
            "source": LeadSource.REFERRAL,
            "source_detail": "",
            "interest": "Wi-Fi upgrade",
            "stage": LeadStage.NEW,
        },
    )
    assert resp.status_code == 302
    lead = Lead.objects.get(name="Ivy")
    assert lead.source == LeadSource.REFERRAL


@pytest.mark.django_db
def test_portal_convert_creates_client(auth_client):
    lead = Lead.objects.create(name="Jude", email="j@example.com")
    resp = auth_client.post(reverse("portal:lead_convert", args=[lead.pk]))
    assert resp.status_code == 302
    lead.refresh_from_db()
    assert lead.converted_client_id is not None
    assert resp.url.endswith(f"/clients/{lead.converted_client_id}/")


@pytest.mark.django_db
def test_portal_blocks_client_users(client, db, client_record):
    from accounts.models import User

    cu = User.objects.create_user(
        email="cu@example.com",
        password="password123",
        role=User.Role.CLIENT,
        client=client_record,
    )
    client.force_login(cu)
    resp = client.get(reverse("portal:lead_list"))
    # Client users get bounced back to the dashboard.
    assert resp.status_code == 302
    assert "/dashboard/" in resp.url


# -----------------------------------------------------------------
# API
# -----------------------------------------------------------------


@pytest.fixture
def api(engineer_user):
    api = APIClient()
    api.force_authenticate(engineer_user)
    return api


@pytest.mark.django_db
def test_api_create_lead(api):
    resp = api.post(
        "/api/v1/leads/leads/",
        data={
            "name": "Kira",
            "email": "kira@example.com",
            "source": LeadSource.WEBSITE,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert resp.data["stage"] == LeadStage.NEW


@pytest.mark.django_db
def test_api_advance_stage(api):
    lead = Lead.objects.create(name="Liam")
    resp = api.post(
        f"/api/v1/leads/leads/{lead.pk}/advance/",
        data={"stage": LeadStage.QUALIFIED},
        format="json",
    )
    assert resp.status_code == 200
    lead.refresh_from_db()
    assert lead.stage == LeadStage.QUALIFIED


@pytest.mark.django_db
def test_api_convert_returns_client_id(api):
    lead = Lead.objects.create(name="Mira")
    resp = api.post(f"/api/v1/leads/leads/{lead.pk}/convert/")
    assert resp.status_code == 200
    assert "client_id" in resp.data
    assert resp.data["client_id"] is not None


@pytest.mark.django_db
def test_api_add_activity(api):
    lead = Lead.objects.create(name="Nico")
    resp = api.post(
        f"/api/v1/leads/leads/{lead.pk}/activities/",
        data={"kind": ActivityKind.CALL, "body": "Called and left voicemail"},
        format="json",
    )
    assert resp.status_code == 201
    assert LeadActivity.objects.filter(
        lead=lead, kind=ActivityKind.CALL
    ).count() == 1


@pytest.mark.django_db
def test_api_blocks_client_users(client_record):
    from accounts.models import User

    cu = User.objects.create_user(
        email="cu2@example.com",
        password="password123",
        role=User.Role.CLIENT,
        client=client_record,
    )
    api = APIClient()
    api.force_authenticate(cu)
    resp = api.get("/api/v1/leads/leads/")
    assert resp.status_code == 403


# -----------------------------------------------------------------
# Follow-up reminders task
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_reminder_task_notifies_assigned_engineer(engineer_user):
    past = timezone.now() - timedelta(hours=2)
    lead = Lead.objects.create(
        name="Olive",
        stage=LeadStage.CONTACTED,
        next_action_at=past,
        assigned_to=engineer_user,
    )
    from .tasks import send_followup_reminders

    result = send_followup_reminders()
    assert "1 notifications" in result
    notif = Notification.objects.filter(
        user=engineer_user, type=Notification.Type.LEAD_REMINDER
    ).first()
    assert notif is not None
    assert lead.name in notif.title

    lead.refresh_from_db()
    assert lead.last_reminded_at is not None


@pytest.mark.django_db
def test_reminder_dedupes_within_window(engineer_user):
    past = timezone.now() - timedelta(hours=2)
    Lead.objects.create(
        name="Pete",
        stage=LeadStage.CONTACTED,
        next_action_at=past,
        assigned_to=engineer_user,
    )
    from .tasks import send_followup_reminders

    send_followup_reminders()
    send_followup_reminders()
    assert Notification.objects.filter(
        type=Notification.Type.LEAD_REMINDER
    ).count() == 1


@pytest.mark.django_db
def test_reminder_skips_won_leads(engineer_user):
    past = timezone.now() - timedelta(hours=2)
    Lead.objects.create(
        name="Quinn",
        stage=LeadStage.WON,
        next_action_at=past,
        assigned_to=engineer_user,
    )
    from .tasks import send_followup_reminders

    send_followup_reminders()
    assert Notification.objects.filter(
        type=Notification.Type.LEAD_REMINDER
    ).count() == 0


@pytest.mark.django_db
def test_reminder_fans_out_to_all_staff_when_unassigned(
    engineer_user, admin_user
):
    past = timezone.now() - timedelta(hours=2)
    Lead.objects.create(
        name="Rosa", stage=LeadStage.NEW, next_action_at=past
    )
    from .tasks import send_followup_reminders

    send_followup_reminders()
    assert Notification.objects.filter(
        type=Notification.Type.LEAD_REMINDER, user=engineer_user
    ).count() == 1
    assert Notification.objects.filter(
        type=Notification.Type.LEAD_REMINDER, user=admin_user
    ).count() == 1


# -----------------------------------------------------------------
# Public contact form (A4)
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_contact_form_renders(client):
    resp = client.get("/contact/")
    assert resp.status_code == 200
    assert b"name=\"name\"" in resp.content
    assert b"name=\"website\"" in resp.content  # honeypot present


@pytest.mark.django_db
def test_contact_form_creates_website_lead(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/",
        data={
            "name": "Sammy",
            "email": "sammy@example.com",
            "phone": "",
            "company": "Sammy Ltd",
            "message": "I want a UniFi network please.",
            "website": "",
        },
    )
    assert resp.status_code == 200
    lead = Lead.objects.get(name="Sammy")
    assert lead.source == LeadSource.WEBSITE
    assert lead.email == "sammy@example.com"
    assert "UniFi" in lead.interest


@pytest.mark.django_db
def test_contact_form_with_ref_tags_referral(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/?ref=LUMA-MARCO-7K2",
        data={
            "name": "Tarja",
            "email": "tarja@example.com",
            "message": "Heard about you from a friend.",
            "website": "",
        },
    )
    assert resp.status_code == 200
    lead = Lead.objects.get(name="Tarja")
    assert lead.source == LeadSource.REFERRAL
    assert "LUMA-MARCO-7K2" in lead.source_detail


@pytest.mark.django_db
def test_contact_form_honeypot_silently_drops(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/",
        data={
            "name": "BotBot",
            "email": "bot@example.com",
            "message": "spam payload",
            "website": "https://spam.example",  # honeypot filled
        },
    )
    assert resp.status_code == 200
    # Pretended success but no Lead written.
    assert Lead.objects.filter(name="BotBot").count() == 0


@pytest.mark.django_db
def test_contact_form_requires_name(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/",
        data={"name": "", "email": "a@b.c", "message": "hi"},
    )
    assert resp.status_code == 200
    assert b"Please tell us your name" in resp.content
    assert Lead.objects.count() == 0


@pytest.mark.django_db
def test_contact_form_requires_email_or_phone(client):
    from django.core.cache import cache

    cache.clear()
    resp = client.post(
        "/contact/",
        data={"name": "Una", "email": "", "phone": "", "message": "hi"},
    )
    assert resp.status_code == 200
    assert Lead.objects.count() == 0


@pytest.mark.django_db
def test_contact_form_rate_limits_repeat_posts(client):
    from django.core.cache import cache

    cache.clear()
    payload = {
        "name": "Vince",
        "email": "v@example.com",
        "message": "hello",
        "website": "",
    }
    first = client.post("/contact/", data=payload)
    assert first.status_code == 200
    second = client.post(
        "/contact/", data={**payload, "name": "Wendy"}, REMOTE_ADDR="127.0.0.1"
    )
    assert second.status_code == 429
    assert Lead.objects.filter(name="Wendy").count() == 0


# -----------------------------------------------------------------
# Inbound IMAP → Lead (A5)
# -----------------------------------------------------------------


@pytest.mark.django_db
def test_inbound_unknown_sender_creates_lead():
    from tickets.inbound import ingest

    raw = (
        b"From: Pat Reilly <pat@stranger.test>\r\n"
        b"To: support@lumatechsolutions.co.uk\r\n"
        b"Subject: New build wiring quote?\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Hi, can you quote me for cabling a 4-bed new build?\r\n"
    )
    result = ingest(raw)
    assert result.ticket is None
    assert result.lead is not None
    lead = Lead.objects.get(email="pat@stranger.test")
    assert lead.name == "Pat Reilly"
    assert lead.source == LeadSource.INBOUND_EMAIL
    assert "cabling" in lead.interest


@pytest.mark.django_db
def test_inbound_known_sender_does_not_create_lead(client_record):
    from accounts.models import User
    from tickets.inbound import ingest

    User.objects.create_user(
        email="cu@acme.test",
        password="x",
        role=User.Role.CLIENT,
        client=client_record,
    )
    raw = (
        b"From: cu@acme.test\r\n"
        b"To: support@lumatechsolutions.co.uk\r\n"
        b"Subject: Wifi flaky\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"It dropped twice this morning.\r\n"
    )
    result = ingest(raw)
    assert result.ticket is not None  # opened a ticket as before
    assert result.lead is None
    assert Lead.objects.count() == 0
