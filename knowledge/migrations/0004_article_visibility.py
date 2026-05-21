from django.db import migrations, models


def _backfill_visibility(apps, schema_editor):
    Article = apps.get_model("knowledge", "Article")
    Article.objects.filter(client_visible=True).update(visibility="all_clients")
    Article.objects.filter(client_visible=False).update(visibility="internal")


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0010_client_stripe_customer_id"),
        ("knowledge", "0003_article_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("internal", "Internal (staff only)"),
                    ("all_clients", "All clients"),
                    ("specific_clients", "Specific clients"),
                ],
                default="internal",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="article",
            name="allowed_clients",
            field=models.ManyToManyField(
                blank=True,
                help_text="Used when visibility=specific_clients.",
                related_name="visible_articles",
                to="clients.client",
            ),
        ),
        migrations.RunPython(_backfill_visibility, _noop_reverse),
    ]
