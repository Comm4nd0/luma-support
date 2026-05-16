"""Django settings for luma_support project."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1,0.0.0.0",
    cast=Csv(),
)

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "djoser",
    "corsheaders",
    "django_filters",
    "channels",
    "django_extensions",
    # Local
    "accounts",
    "audit",
    "billing",
    "clients",
    "tickets",
    "knowledge",
    "notifications",
    "system",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "luma_support.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "luma_support.context.brand",
            ],
        },
    },
]

WSGI_APPLICATION = "luma_support.wsgi.application"
ASGI_APPLICATION = "luma_support.asgi.application"

# --- Database -----------------------------------------------------------
# Use SQLite as a fallback when POSTGRES_HOST is unset (e.g. running
# tests outside Docker); use Postgres in normal operation.
if config("POSTGRES_HOST", default=""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB", default="luma_support"),
            "USER": config("POSTGRES_USER", default="luma"),
            "PASSWORD": config("POSTGRES_PASSWORD", default="luma"),
            "HOST": config("POSTGRES_HOST", default="postgres"),
            "PORT": config("POSTGRES_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Auth ---------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "portal:login"
LOGIN_REDIRECT_URL = "portal:dashboard"
LOGOUT_REDIRECT_URL = "portal:login"

# --- I18N ---------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

# --- Static / media -----------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON", default="60/min"),
        "user": config("THROTTLE_USER", default="1000/hour"),
        "auth": config("THROTTLE_AUTH", default="10/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_LIFETIME_MINUTES", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_LIFETIME_DAYS", default=7, cast=int)
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

DJOSER = {
    "USER_ID_FIELD": "id",
    "LOGIN_FIELD": "email",
    "USER_CREATE_PASSWORD_RETYPE": False,
    "SERIALIZERS": {
        "user": "accounts.serializers.UserSerializer",
        "current_user": "accounts.serializers.UserSerializer",
        "user_create": "accounts.serializers.UserCreateSerializer",
    },
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:8006,http://127.0.0.1:8006",
    cast=Csv(),
)

# --- Channels / Redis ---------------------------------------------------
REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# --- Celery -------------------------------------------------------------
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://redis:6379/2"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "sla-warning-check": {
        "task": "notifications.tasks.check_sla_warnings",
        "schedule": timedelta(minutes=5),
    },
    "generate-contract-invoices": {
        "task": "billing.tasks.generate_contract_invoices",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },
    "sync-xero-payments": {
        "task": "billing.tasks.sync_xero_payments",
        "schedule": timedelta(minutes=15),
    },
    "poll-inbound-mail": {
        "task": "tickets.tasks.poll_inbound_mail",
        "schedule": timedelta(seconds=60),
    },
    "generate-scheduled-tickets": {
        "task": "tickets.tasks.generate_scheduled_tickets",
        "schedule": crontab(hour=6, minute=0),
    },
}

# --- Email --------------------------------------------------------------
EMAIL_BACKEND = config(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="support@lumatechsolutions.co.uk"
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)

# --- Inbound mail (email-to-ticket) -------------------------------------
# When INBOUND_IMAP_HOST is empty, the tickets.tasks.poll_inbound_mail
# task no-ops, so dev and CI don't try to reach an IMAP server.
# Replies are matched via plus-addressing on the outbound Reply-To
# (e.g. support+42@lumatechsolutions.co.uk).
INBOUND_IMAP_HOST = config("INBOUND_IMAP_HOST", default="")
INBOUND_IMAP_PORT = config("INBOUND_IMAP_PORT", default=993, cast=int)
INBOUND_IMAP_USER = config("INBOUND_IMAP_USER", default="")
INBOUND_IMAP_PASSWORD = config("INBOUND_IMAP_PASSWORD", default="")
INBOUND_IMAP_MAILBOX = config("INBOUND_IMAP_MAILBOX", default="INBOX")

# --- Encryption ---------------------------------------------------------
# Used by clients.System.credentials_encrypted and
# billing.XeroConnection.refresh_token_encrypted. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#
# FERNET_KEYS (comma-separated, primary first) is the recommended form
# and supports rotation: prepend a new key, run
# `python manage.py rotate_fernet_keys` to re-encrypt all stored
# ciphertexts, then drop the old key. FERNET_KEY is the legacy single-
# key alias and is honoured when FERNET_KEYS is empty.
FERNET_KEYS = config("FERNET_KEYS", default="")
FERNET_KEY = config(
    "FERNET_KEY", default="aXzDcRGfQa8H_wK3UZ4xG4LnkZbNz7q6uhZWqXoJZ5o="
)

# --- Push notifications --------------------------------------------------
# Mobile app push goes through Firebase Cloud Messaging (FCM HTTP v1).
# APNs is delivered via the same FCM project (upload the .p8 in the
# Firebase console). FCM_ENABLED gates the whole stack so dev and CI
# don't try to reach Firebase.
FCM_ENABLED = config("FCM_ENABLED", default=False, cast=bool)
FIREBASE_CREDENTIALS_JSON = config("FIREBASE_CREDENTIALS_JSON", default="")

# --- Site ---------------------------------------------------------------
SITE_URL = config("SITE_URL", default="http://localhost:8006")

# --- Billing / Xero -----------------------------------------------------
DEFAULT_HOURLY_RATE = config("DEFAULT_HOURLY_RATE", default="75.00", cast=Decimal)
DEFAULT_CURRENCY = config("DEFAULT_CURRENCY", default="GBP")
DEFAULT_TAX_TYPE = config("DEFAULT_TAX_TYPE", default="OUTPUT2")
DEFAULT_ACCOUNT_CODE = config("DEFAULT_ACCOUNT_CODE", default="200")

XERO_CLIENT_ID = config("XERO_CLIENT_ID", default="")
XERO_CLIENT_SECRET = config("XERO_CLIENT_SECRET", default="")
XERO_REDIRECT_URI = config(
    "XERO_REDIRECT_URI", default=f"{SITE_URL}/billing/xero/oauth/callback/"
)
XERO_SCOPES = config(
    "XERO_SCOPES",
    default="offline_access accounting.contacts accounting.transactions",
)

# --- Stripe -------------------------------------------------------------
# Leave STRIPE_API_KEY empty to disable the payment-link flow; the
# create_stripe_payment_link task no-ops in that case. STRIPE_WEBHOOK_SECRET
# is the signing secret from https://dashboard.stripe.com/webhooks for
# the endpoint POST /api/v1/billing/webhooks/stripe/.
STRIPE_API_KEY = config("STRIPE_API_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

# --- Logging ------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
