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
