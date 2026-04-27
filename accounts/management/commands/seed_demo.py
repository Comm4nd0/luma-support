"""Populate the database with demo data so the portal is usable on day one.

Idempotent — running it twice gives you the same result, not duplicates.

Usage:
    python manage.py seed_demo
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from clients.models import CarePlanTier, Client, System, SystemType
from knowledge.models import Article
from tickets.models import Ticket


class Command(BaseCommand):
    help = "Seed demo clients, systems, users, tickets, and KB articles."

    def handle(self, *args, **options):
        User = get_user_model()

        # --- Users -----------------------------------------------------
        admin, _ = User.objects.get_or_create(
            email="marco@lumatechsolutions.co.uk",
            defaults={
                "first_name": "Marco",
                "last_name": "Baldanza",
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if not admin.has_usable_password():
            admin.set_password("luma_admin_password")
            admin.save()
            self.stdout.write("  · admin password set to: luma_admin_password")

        engineer, _ = User.objects.get_or_create(
            email="engineer@lumatechsolutions.co.uk",
            defaults={
                "first_name": "Demo",
                "last_name": "Engineer",
                "role": "engineer",
                "is_staff": True,
            },
        )
        if not engineer.has_usable_password():
            engineer.set_password("luma_engineer_password")
            engineer.save()

        # --- Clients ---------------------------------------------------
        clients_def = [
            ("Acme Coffee Roasters", "Acme Ltd", CarePlanTier.PROFESSIONAL),
            ("Greenfield Manor", "Greenfield Estates", CarePlanTier.ENTERPRISE),
            ("Brightside Boutique", "Brightside Ltd", CarePlanTier.ESSENTIAL),
            ("OneOff Plumbing", "", CarePlanTier.NONE),
        ]
        clients = []
        for name, company, tier in clients_def:
            c, _ = Client.objects.get_or_create(
                name=name,
                defaults={
                    "company": company,
                    "email": name.lower().split()[0] + "@example.com",
                    "phone": "+44 1234 567890",
                    "address": "1 Demo Lane\nDemo Town\nUK",
                    "care_plan_tier": tier,
                    "care_plan_start": date.today() - timedelta(days=180),
                    "care_plan_renewal": date.today() + timedelta(days=185),
                    "notes": f"Seeded demo client ({tier}).",
                },
            )
            clients.append(c)

        # --- Systems ---------------------------------------------------
        systems_def = [
            (clients[0], SystemType.NETWORK, "UniFi network"),
            (clients[0], SystemType.WEBSITE, "Acme website"),
            (clients[1], SystemType.AUTOMATION, "Home automation hub"),
            (clients[1], SystemType.SECURITY, "CCTV"),
            (clients[2], SystemType.WEBSITE, "Boutique store"),
        ]
        systems = []
        for client, type_, name in systems_def:
            s, _ = System.objects.get_or_create(
                client=client,
                name=name,
                defaults={
                    "type": type_,
                    "description": f"Demo {type_} system",
                    "installed_date": date.today() - timedelta(days=120),
                    "monitoring_url": "https://example.com/monitor",
                    "devices_json": {"devices": []},
                },
            )
            systems.append(s)

        # --- Tickets ---------------------------------------------------
        tickets_def = [
            (clients[1], "Lights not responding in lounge", "critical", "in_progress"),
            (clients[0], "Wi-Fi dropping in back office", "high", "assigned"),
            (clients[0], "Add staff member to email list", "medium", "new"),
            (clients[2], "404 on /shop page", "medium", "waiting"),
            (clients[3], "Quote request — small office network", "low", "new"),
        ]
        for client, subject, priority, status in tickets_def:
            existing = Ticket.objects.filter(client=client, subject=subject).first()
            if existing:
                continue
            t = Ticket(
                client=client,
                subject=subject,
                description=f"Demo ticket: {subject}",
                priority=priority,
                status=status,
                assigned_to=engineer if status != "new" else None,
                created_by=admin,
            )
            t.save()
            # Backdate one for variety so SLA shows interesting state.
            if subject.startswith("Lights"):
                Ticket.objects.filter(pk=t.pk).update(
                    created_at=timezone.now() - timedelta(hours=3),
                    sla_deadline=timezone.now() - timedelta(hours=1),
                )

        # --- Knowledge articles ----------------------------------------
        articles_def = [
            (
                "How we triage tickets",
                "general",
                "Tickets are auto-prioritised based on the client's care plan tier. "
                "Critical = 2hr SLA, High = 4hr, Medium = 24hr, Low = 48hr.",
                False,
            ),
            (
                "UniFi: factory reset an access point",
                "network",
                "1. Hold the reset button for 10 seconds.\n2. Wait for the LED to flash.\n3. Re-adopt in the controller.",
                True,
            ),
        ]
        for title, category, content, visible in articles_def:
            Article.objects.get_or_create(
                title=title,
                defaults={
                    "category": category,
                    "content": content,
                    "client_visible": visible,
                    "published_at": timezone.now(),
                },
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        self.stdout.write("  Admin login: marco@lumatechsolutions.co.uk / luma_admin_password")
        self.stdout.write("  Engineer login: engineer@lumatechsolutions.co.uk / luma_engineer_password")
