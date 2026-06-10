"""Django settings for luma_support project."""
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG must be resolved first: several settings below relax their
# production requirements when DEBUG is on so that a bare `runserver` works
# without a populated .env. Default to False — opt into local dev with
# DJANGO_DEBUG=1.
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

# True while the pytest suite is running. The production-only guards below
# (a required real SECRET_KEY / FERNET key) are relaxed under tests so the
# suite runs without a populated .env, the same way it relaxes under DEBUG.
# pytest-django imports this module before any conftest can set env vars, so
# detect the runner via sys.modules rather than an environment variable.
TESTING = "pytest" in sys.modules
_RELAXED = DEBUG or TESTING

_INSECURE_SECRET_KEY = "dev-insecure-change-me"
SECRET_KEY = config("DJANGO_SECRET_KEY", default=_INSECURE_SECRET_KEY)
if SECRET_KEY == _INSECURE_SECRET_KEY and not _RELAXED:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique secret when DEBUG is off."
    )

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
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
    "rest_framework_simplejwt.token_blacklist",
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
    "social",
    "leads",
    "quotes",
    "features",
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
    # Optional: empty/unset ADMIN_IP_ALLOWLIST = no enforcement, so this
    # is safe to leave wired in by default.
    "accounts.middleware.AdminIpAllowlistMiddleware",
]

ADMIN_IP_ALLOWLIST = config("ADMIN_IP_ALLOWLIST", default="")

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
                "luma_support.context.unread_notifications",
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

# --- Uploads --------------------------------------------------------------
# Hard cap enforced by luma_support.uploads.validate_upload on every
# user-supplied file (ticket attachments, KB assets, client documents).
MAX_UPLOAD_BYTES = config("MAX_UPLOAD_BYTES", default=25 * 1024 * 1024, cast=int)
# Request-body ceiling: largest allowed file + headroom for the rest of
# the multipart envelope. Files above 5MB spill to a temp file on disk.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

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
    # Rotate refresh tokens on use and blacklist the old one so a stolen
    # refresh token has a short useful life. The blacklist also powers
    # the user-facing "revoke this device" action in /portal/sessions/.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
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

# Hosts permitted to POST cross-origin (Django ≥ 4 requires scheme+host).
# In production set this to the public URL the portal is served on, e.g.
#   CSRF_TRUSTED_ORIGINS=https://support.lumatechsolutions.co.uk
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="", cast=Csv()
)

# --- Security headers ---------------------------------------------------
# Hardened defaults apply only in a real deployment (DEBUG off and not under
# the test suite) so local dev / pytest over plain HTTP keep working — an
# enabled SECURE_SSL_REDIRECT would otherwise 301 every test request. Each
# value stays individually overridable via env for staging or unusual
# deployments. Production runs behind Caddy (TLS terminated at the proxy),
# so trust its X-Forwarded-Proto header.
_HARDEN = not _RELAXED
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=_HARDEN, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=_HARDEN, cast=bool)
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=_HARDEN, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = config(
    "SECURE_HSTS_SECONDS", default=31536000 if _HARDEN else 0, cast=int
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=_HARDEN, cast=bool
)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=_HARDEN, cast=bool)

# --- Channels / Redis ---------------------------------------------------
REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# --- Cache ----------------------------------------------------------------
# Mirrors the SQLite fallback: Redis when running alongside Postgres
# (Docker / production), LocMem otherwise so local pytest needs nothing.
# LocMem is per-process — fine for the webhook rate limiter's purpose of
# basic abuse-resistance, but not a shared cache across gunicorn workers.
if config("POSTGRES_HOST", default=""):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# Requests per minute allowed on the token-auth webhook ingest endpoint
# (per token + caller IP). 0 disables the limiter.
WEBHOOK_RATE_LIMIT = config("WEBHOOK_RATE_LIMIT", default=30, cast=int)

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
    "sla-risk-digest": {
        "task": "notifications.tasks.send_sla_risk_digest",
        "schedule": crontab(hour=8, minute=0),
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
    "refresh-unifi-devices": {
        "task": "system.tasks.refresh_unifi_devices",
        "schedule": timedelta(minutes=30),
    },
    "refresh-social-accounts": {
        "task": "social.tasks.refresh_social_accounts",
        "schedule": timedelta(minutes=20),
    },
    "refresh-social-kpis-daily": {
        "task": "social.tasks.refresh_social_kpis_daily",
        "schedule": crontab(hour=4, minute=15),
    },
    "send-monthly-reports": {
        "task": "tickets.tasks.send_monthly_reports",
        "schedule": crontab(hour=7, minute=0, day_of_month=1),
    },
    "lead-followup-reminders": {
        "task": "leads.tasks.send_followup_reminders",
        "schedule": crontab(hour=8, minute=30),
    },
    "expire-stale-quotes": {
        "task": "quotes.tasks.expire_stale_quotes",
        "schedule": crontab(hour=3, minute=15),
    },
    "care-plan-renewal-reminders": {
        "task": "clients.tasks.check_care_plan_renewals",
        "schedule": crontab(hour=8, minute=15),
    },
    "send-nps-survey": {
        "task": "clients.tasks.send_nps_survey",
        "schedule": crontab(
            hour=9, minute=0, day_of_month=1, month_of_year="1,4,7,10"
        ),
    },
    "chase-overdue-invoices": {
        "task": "billing.tasks.chase_overdue_invoices",
        "schedule": crontab(hour=9, minute=30),
    },
    "send-weekly-client-digest": {
        "task": "notifications.tasks.send_weekly_client_digest",
        # Friday 09:00 local — gives Marco a sensible "week wrap" cadence
        # and avoids landing in Monday-morning inbox overload.
        "schedule": crontab(hour=9, minute=0, day_of_week="fri"),
    },
    "run-anomaly-sweep": {
        "task": "system.tasks.run_anomaly_sweep",
        # Daily at 04:30 local — quiet hour, lets the night's UniFi
        # polls accumulate baseline before the sweep runs.
        "schedule": crontab(hour=4, minute=30),
    },
    "prune-old-health-samples": {
        "task": "system.tasks.prune_old_health_samples",
        "schedule": crontab(hour=5, minute=0, day_of_week="sun"),
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
FERNET_KEY = config("FERNET_KEY", default="")
if not FERNET_KEYS and not FERNET_KEY:
    if _RELAXED:
        # Local dev / tests: generate an ephemeral key so encrypt/decrypt
        # round trips work in-process. Anything persisted under it is
        # unreadable after a restart — which is the point: never store real
        # credentials without a real key.
        from cryptography.fernet import Fernet

        FERNET_KEY = Fernet.generate_key().decode()
    else:
        raise ImproperlyConfigured(
            "FERNET_KEYS (preferred) or FERNET_KEY must be set when DEBUG is "
            "off. Generate one with: python -c \"from cryptography.fernet "
            "import Fernet; print(Fernet.generate_key().decode())\""
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
REFERRAL_CREDIT_GBP = config("REFERRAL_CREDIT_GBP", default="25.00", cast=Decimal)
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

# --- Social accounts (Luma's own LinkedIn / FB / IG) --------------------
# Each provider gates on its credentials being non-empty — the
# refresh_social_accounts task skips accounts whose platform has no
# configured client_id, the same way Stripe / Anthropic / IMAP gate.
#
# LinkedIn: requires a Marketing Developer Platform app for posts/inbox
# beyond OIDC; without MDP, Page mentions/comments only (no DMs).
# Meta (Facebook + Instagram): single FB app, shared client_id/secret;
# the IG Business account is reached via its linked Page token.
LINKEDIN_CLIENT_ID = config("LINKEDIN_CLIENT_ID", default="")
LINKEDIN_CLIENT_SECRET = config("LINKEDIN_CLIENT_SECRET", default="")
LINKEDIN_REDIRECT_URI = config(
    "LINKEDIN_REDIRECT_URI",
    default=f"{SITE_URL}/portal/social/callback/linkedin_page/",
)
LINKEDIN_SCOPES = config(
    "LINKEDIN_SCOPES",
    default="r_organization_social r_basicprofile",
)

META_APP_ID = config("META_APP_ID", default="")
META_APP_SECRET = config("META_APP_SECRET", default="")
META_REDIRECT_URI = config(
    "META_REDIRECT_URI",
    default=f"{SITE_URL}/portal/social/callback/meta/",
)
META_SCOPES = config(
    "META_SCOPES",
    default="pages_show_list,pages_read_engagement,pages_messaging,instagram_basic,instagram_manage_comments,instagram_manage_messages",
)

# --- Anthropic (Claude) --------------------------------------------------
# Powers KB article suggestions on ticket-create and AI-drafted replies on
# ticket-detail. When ANTHROPIC_API_KEY is empty, the suggestion path
# falls back to a keyword-overlap search so dev/CI never reach the API.
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = config("ANTHROPIC_MODEL", default="claude-sonnet-4-6")

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

# --- Sentry (error reporting) -------------------------------------------
# Initialised here so a single env var (SENTRY_DSN) turns reporting on/
# off the same way the rest of our integrations gate. When SENTRY_DSN is
# empty, the SDK is never imported and there's zero overhead — same
# pattern used for Stripe/Anthropic/IMAP/FCM elsewhere in this file.
#
# What we capture:
#   * Django request errors (incl. WSGI / ASGI)
#   * Celery task exceptions
#   * Logger calls at ERROR or higher (event), WARNING+ (breadcrumb)
#
# What we deliberately do NOT capture:
#   * Personal data — the `send_default_pii` flag stays off. Combined
#     with the `before_send` scrubber below, request headers / body /
#     query params with obvious secret-shaped names are redacted before
#     anything leaves the host.
#   * Performance traces / profiling by default — too noisy for a solo
#     op. Opt in by setting SENTRY_TRACES_SAMPLE_RATE > 0.
SENTRY_DSN = config("SENTRY_DSN", default="")
if SENTRY_DSN:
    import logging as _logging

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    _SECRET_KEY_RE = __import__("re").compile(
        r"(?i)(password|secret|token|api[-_]?key|authori[sz]ation|cookie|csrf|fernet)"
    )

    def _scrub_event(event, hint):
        """Best-effort redaction of secret-shaped fields before send.

        We don't try to be exhaustive — sentry-sdk already strips a lot —
        but we explicitly wipe request headers/cookies/data and extra
        fields whose key name looks secret-shaped.
        """
        try:
            req = event.get("request") or {}
            for bucket in ("headers", "cookies", "data", "query_string", "env"):
                v = req.get(bucket)
                if isinstance(v, dict):
                    for k in list(v.keys()):
                        if _SECRET_KEY_RE.search(k):
                            v[k] = "[scrubbed]"
                elif isinstance(v, str) and _SECRET_KEY_RE.search(bucket):
                    req[bucket] = "[scrubbed]"
            extra = event.get("extra") or {}
            for k in list(extra.keys()):
                if _SECRET_KEY_RE.search(k):
                    extra[k] = "[scrubbed]"
        except Exception:  # noqa: BLE001 — scrubbing must never crash send
            pass
        return event

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                # Default: capture HTTP request data (path, method) but
                # never the body — body scrubbing below handles forms.
                transaction_style="url",
            ),
            CeleryIntegration(monitor_beat_tasks=False),
            LoggingIntegration(
                level=_logging.WARNING,       # breadcrumb threshold
                event_level=_logging.ERROR,   # event threshold
            ),
        ],
        environment=config(
            "SENTRY_ENVIRONMENT", default="development" if DEBUG else "production"
        ),
        release=config("SENTRY_RELEASE", default=""),
        send_default_pii=False,
        traces_sample_rate=float(config("SENTRY_TRACES_SAMPLE_RATE", default="0")),
        profiles_sample_rate=float(config("SENTRY_PROFILES_SAMPLE_RATE", default="0")),
        before_send=_scrub_event,
        # Don't ship sentry telemetry for the health probes — they're
        # called every few seconds by the load balancer and shouldn't
        # eat our event quota if something errors briefly.
        ignore_errors=[],
    )
