"""Snapshot Article body changes into ArticleRevision rows.

The pre_save handler captures the old (title, content) and a post_save
handler writes a revision only when one of those fields changed —
avoids creating noise revisions when only ``published_at`` or
``category`` move.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Article, ArticleRevision


@receiver(pre_save, sender=Article)
def _capture_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._kb_old_title = None
        instance._kb_old_content = None
        return
    try:
        prior = Article.objects.only("title", "content").get(pk=instance.pk)
        instance._kb_old_title = prior.title
        instance._kb_old_content = prior.content
    except Article.DoesNotExist:
        instance._kb_old_title = None
        instance._kb_old_content = None


@receiver(post_save, sender=Article)
def _snapshot_on_change(sender, instance, created, **kwargs):
    if created:
        # First revision = the article's birth state.
        ArticleRevision.objects.create(
            article=instance, title=instance.title, content=instance.content
        )
        return
    old_title = getattr(instance, "_kb_old_title", None)
    old_content = getattr(instance, "_kb_old_content", None)
    if old_title == instance.title and old_content == instance.content:
        return
    # Snapshot the *previous* state so the revisions list reads as a
    # history of "what this used to be".
    ArticleRevision.objects.create(
        article=instance,
        title=old_title if old_title is not None else instance.title,
        content=old_content if old_content is not None else instance.content,
    )
