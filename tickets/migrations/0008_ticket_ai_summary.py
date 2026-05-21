from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0007_ticket_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="ai_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="ai_summary_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
