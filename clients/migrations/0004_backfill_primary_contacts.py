"""Backfill a primary Contact row for every existing Client.

The Client model keeps name/email/phone as the canonical primary
contact info; this data migration mirrors that into a Contact row so
the new multi-contact UI shows existing clients consistently from day
one.
"""
from django.db import migrations


def create_primary_contacts(apps, schema_editor):
    Client = apps.get_model("clients", "Client")
    Contact = apps.get_model("clients", "Contact")
    for client in Client.objects.all():
        if client.contacts.filter(is_primary=True).exists():
            continue
        Contact.objects.create(
            client=client,
            name=client.name,
            email=client.email,
            phone=client.phone,
            is_primary=True,
        )


def remove_primary_contacts(apps, schema_editor):
    Contact = apps.get_model("clients", "Contact")
    Contact.objects.filter(is_primary=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0003_contact"),
    ]

    operations = [
        migrations.RunPython(create_primary_contacts, remove_primary_contacts),
    ]
