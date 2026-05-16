from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0004_backfill_primary_contacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="system",
            name="last_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="system",
            name="health_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Unknown"),
                    ("ok", "OK"),
                    ("degraded", "Degraded"),
                    ("down", "Down"),
                ],
                max_length=16,
            ),
        ),
    ]
