import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clients", "0002_billing_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("one_off", "One-off"),
                            ("contract", "Contract"),
                            ("time", "Time-based"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("sent", "Sent"),
                            ("authorised", "Authorised"),
                            ("paid", "Paid"),
                            ("voided", "Voided"),
                        ],
                        default="draft",
                        max_length=16,
                    ),
                ),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                (
                    "subtotal",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                (
                    "tax",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                (
                    "total",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                ("currency", models.CharField(default="GBP", max_length=3)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("xero_invoice_id", models.CharField(blank=True, max_length=64)),
                ("xero_status", models.CharField(blank=True, max_length=24)),
                ("xero_synced_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="invoices",
                        to="clients.client",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invoices_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "contract")),
                fields=("client", "kind", "period_start"),
                name="uniq_contract_invoice_per_period",
            ),
        ),
        migrations.CreateModel(
            name="InvoiceLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("description", models.CharField(max_length=500)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=10)),
                ("unit_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "line_total",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                ("account_code", models.CharField(blank=True, max_length=16)),
                ("tax_type", models.CharField(blank=True, max_length=24)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lines",
                        to="billing.invoice",
                    ),
                ),
                (
                    "time_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="tickets.timeentry",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "xero_payment_id",
                    models.CharField(max_length=64, unique=True),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("paid_at", models.DateTimeField()),
                ("reference", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="billing.invoice",
                    ),
                ),
            ],
            options={"ordering": ["-paid_at"]},
        ),
        migrations.CreateModel(
            name="XeroConnection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("tenant_id", models.CharField(max_length=64)),
                ("refresh_token_encrypted", models.TextField()),
                ("access_token", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField()),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                (
                    "connected_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"verbose_name": "Xero connection"},
        ),
    ]
