from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="customer_type",
            field=models.CharField(
                choices=[("home", "Home"), ("business", "Business")],
                default="home",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="vat_number",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="client",
            name="billing_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="client",
            name="hourly_rate",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="monthly_fee",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="xero_contact_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="client",
            name="xero_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
