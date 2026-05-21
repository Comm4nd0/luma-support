from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published_at__isnull=False, published_at__lte=timezone.now())

    def visible_to_clients(self):
        return self.published().filter(client_visible=True)


class Article(models.Model):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        NETWORK = "network", "Network"
        AUTOMATION = "automation", "Home Automation"
        WEBSITE = "website", "Website"
        APP = "app", "App"
        SECURITY = "security", "Security"

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    content = models.TextField(help_text="Markdown")
    category = models.CharField(
        max_length=16, choices=Category.choices, default=Category.GENERAL
    )
    client_visible = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ArticleQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:300] or "article"
            slug = base
            counter = 2
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def is_published(self) -> bool:
        return (
            self.published_at is not None
            and self.published_at <= timezone.now()
        )


class ArticleRevision(models.Model):
    """Frozen snapshot of an Article's body whenever the body changes.

    Written by a post_save signal; supports the "what did this article
    used to say?" / rollback story without bloating the Article row
    itself.
    """

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="revisions"
    )
    title = models.CharField(max_length=300)
    content = models.TextField()
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-edited_at"]
        indexes = [models.Index(fields=["article", "-edited_at"])]

    def __str__(self):
        return f"rev of {self.article_id} @ {self.edited_at:%Y-%m-%d %H:%M}"


class KbSearchLog(models.Model):
    """One row per KB search / suggest request.

    Lets us answer "which topics is Marco being asked about that have no
    article yet?" via a portal report — see the kb-gaps page. Capped
    text length avoids storing pathological inputs.
    """

    query = models.CharField(max_length=500)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    results_count = models.PositiveIntegerField(default=0)
    source = models.CharField(
        max_length=32,
        default="search",
        help_text='"search" for /articles/search/, "suggest" for the AI-ranked draft helper.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["results_count", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.query!r} -> {self.results_count}"
