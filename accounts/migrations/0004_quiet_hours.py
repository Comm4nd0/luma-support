from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_recovery_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="quiet_hours_start",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="quiet_hours_end",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="quiet_hours_critical_override",
            field=models.BooleanField(default=True),
        ),
    ]
