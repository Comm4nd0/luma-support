"""Celery app for luma_support."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "luma_support.settings")

app = Celery("luma_support")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
