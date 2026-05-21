from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_maintenance_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="sla_paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
