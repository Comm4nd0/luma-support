"""WSGI config for luma_support project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "luma_support.settings")

application = get_wsgi_application()
