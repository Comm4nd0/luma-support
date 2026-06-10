"""Client and System models."""
from decimal import Decimal

from django.conf import settings
from django.db import models

from .encryption import decrypt, encrypt


class CarePlanTier(models.TextChoices):
    NONE = "none", "None"
    ESSENTIAL = "essential", "Essential"
    PROFESSIONAL = "professional", "Professional"
    ENTERPRISE = "enterprise", "Enterprise"


class CustomerType(models.TextChoices):
    HOME = "home", "Home"
    BUSINESS = "business", "Business"


class Client(models.Model):
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    customer_type = models.CharField(
        max_length=8, choices=CustomerType.choices, default=CustomerType.HOME
    )
    vat_number = models.CharField(max_length=32, blank=True)
    billing_address = models.TextField(blank=True)

    care_plan_tier = models.CharField(
        max_length=16,
        choices=CarePlanTier.choices,
        default=CarePlanTier.NONE,
        db_index=True,
    )
    care_plan_start = models.DateField(null=True, blank=True)
    care_plan_renewal = models.DateField(null=True, blank=True)

    hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    monthly_fee = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    xero_contact_id = models.CharField(max_length=64, blank=True)
    xero_synced_at = models.DateTimeField(null=True, blank=True)

    # Cached Stripe Customer id — populated lazily the first time we
    # open a customer-portal session for this client.
    stripe_customer_id = models.CharField(max_length=64, blank=True)

    notes = models.TextField(blank=True)

    # Opt-out switch for the Friday-9am client digest email.
    weekly_digest_opt_in = models.BooleanField(default=True)

    # Public per-client uptime page lives at /status/<slug>/. NULL =
    # disabled (so a freshly-created client doesn't accidentally land
    # on a public URL).
    status_page_slug = models.SlugField(
        max_length=80, blank=True, null=True, unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def has_active_care_plan(self) -> bool:
        return self.care_plan_tier != CarePlanTier.NONE

    @property
    def effective_billing_address(self) -> str:
        return self.billing_address or self.address

    def effective_hourly_rate(self) -> Decimal:
        if self.hourly_rate is not None:
            return self.hourly_rate
        return Decimal(str(settings.DEFAULT_HOURLY_RATE))


def _nps_token() -> str:
    """URL-safe random token for one-shot NPS links."""
    import secrets

    return secrets.token_urlsafe(32)


def _referral_code() -> str:
    """Short, human-shareable referral code. Uppercase + digits, no
    confusing letters (O/0/I/1 stripped). Uniqueness checked at save."""
    import secrets

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "LUMA-" + "".join(secrets.choice(alphabet) for _ in range(8))


class ReferralCode(models.Model):
    """A client's word-of-mouth referral code.

    Created lazily the first time the client opens their "Refer a
    friend" page (or via ``ReferralCode.for_client(client)``). The
    balance grows when a referred Lead converts (``referrals.credit``)
    and shrinks when monthly contract invoices apply the credit.
    """

    client = models.OneToOneField(
        "Client",
        on_delete=models.CASCADE,
        related_name="referral_code",
    )
    code = models.CharField(
        max_length=32, unique=True, default=_referral_code
    )
    credit_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    lifetime_credit = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-credit_balance"]

    def __str__(self) -> str:
        return f"{self.code} → {self.client.name}"

    @classmethod
    def for_client(cls, client) -> "ReferralCode":
        """Return (or create) the client's referral code, retrying on collision."""
        existing = cls.objects.filter(client=client).first()
        if existing:
            return existing
        from django.db import IntegrityError

        for _ in range(8):
            try:
                return cls.objects.create(client=client)
            except IntegrityError:
                continue
        # As a last resort, append the client pk to guarantee uniqueness.
        return cls.objects.create(
            client=client, code=f"{_referral_code()}-{client.pk}"
        )


class OnboardingTaskTemplate(models.Model):
    """A reusable item Marco wants done for every new client.

    Seeded once via the data migration; new templates can be added via
    the admin. Each row turns into a `ClientOnboardingTask` instance
    on the new Client when a Lead converts to Won.
    """

    title = models.CharField(max_length=200)
    order = models.PositiveSmallIntegerField(default=0)
    due_offset_days = models.PositiveSmallIntegerField(
        default=7,
        help_text="Days after the client is created when this should be done.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self) -> str:
        return self.title


class ClientOnboardingTask(models.Model):
    """An open or completed item on a specific client's onboarding checklist."""

    client = models.ForeignKey(
        "Client", on_delete=models.CASCADE, related_name="onboarding_tasks"
    )
    title = models.CharField(max_length=200)
    order = models.PositiveSmallIntegerField(default=0)
    due_on = models.DateField(null=True, blank=True)
    done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["done", "order", "pk"]

    def __str__(self) -> str:
        return f"{self.client.name} — {self.title}"


class HealthSample(models.Model):
    """Time-series sample for a monitored system metric.

    Used by ``system.anomaly`` to spot spikes / dips against a rolling
    baseline. Old rows can be pruned by a beat task; the index keeps
    "newest N for a (system, metric)" queries cheap.
    """

    system = models.ForeignKey(
        "System",
        on_delete=models.CASCADE,
        related_name="health_samples",
    )
    metric = models.CharField(max_length=64)
    value = models.FloatField()
    sampled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sampled_at"]
        indexes = [models.Index(fields=["system", "metric", "-sampled_at"])]

    def __str__(self):
        return f"{self.system_id}/{self.metric}={self.value} @{self.sampled_at}"


def _client_document_path(instance, filename):
    return f"client-docs/{instance.client_id}/{filename}"


class ClientDocument(models.Model):
    """File attached to a client account (warranty PDFs, network
    diagrams, contracts, welcome packs).

    Client users see their own client-visible documents; staff manage
    every client's library. ``client_visible=False`` keeps internal
    docs (switch credential references, supplier logins) engineer-only.
    """

    class Kind(models.TextChoices):
        CONTRACT = "contract", "Contract"
        WARRANTY = "warranty", "Warranty"
        DIAGRAM = "diagram", "Diagram"
        WELCOME = "welcome", "Welcome pack"
        OTHER = "other", "Other"

    client = models.ForeignKey(
        "Client", on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to=_client_document_path)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    client_visible = models.BooleanField(
        default=True,
        help_text="Visible to the client's portal users. Disable for internal docs.",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.client.name} — {self.title}"


class SiteVisit(models.Model):
    """GPS-stamped on-site engineer visit.

    The "start" action drops a row with started_at + optional GPS
    coordinates. The "end" action stamps ended_at + end coordinates
    and creates a billable TimeEntry on behalf of the engineer so the
    visit duration shows up in the existing time-tracking surfaces.

    Coordinates are optional everywhere — Marco can use this from a
    desktop without a GPS by just hitting start / end on the buttons.
    """

    client = models.ForeignKey(
        "Client", on_delete=models.PROTECT, related_name="site_visits"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="site_visits",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    lat_start = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    lon_start = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    lat_end = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    lon_end = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    time_entry = models.ForeignKey(
        "tickets.TimeEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.client.name} — {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def duration_minutes(self) -> int | None:
        if not self.ended_at:
            return None
        return max(0, int((self.ended_at - self.started_at).total_seconds() // 60))


def seed_onboarding_tasks(client: "Client") -> int:
    """Materialise the active OnboardingTaskTemplate rows onto a Client.

    Idempotent — running it twice for the same client won't duplicate
    the tasks. Returns the number of tasks created.
    """
    from datetime import timedelta as _td

    from django.utils import timezone as _tz

    existing = set(
        client.onboarding_tasks.values_list("title", flat=True)
    )
    today = _tz.localdate()
    n = 0
    for tpl in OnboardingTaskTemplate.objects.filter(is_active=True):
        if tpl.title in existing:
            continue
        ClientOnboardingTask.objects.create(
            client=client,
            title=tpl.title,
            order=tpl.order,
            due_on=today + _td(days=tpl.due_offset_days),
        )
        n += 1
    return n


class NpsResponse(models.Model):
    """Quarterly Net Promoter Score survey.

    A row is created per `client` per quarter when the
    `send_nps_survey` beat task fires. The recipient hits
    `/nps/<token>/` to submit a single 0-10 score (and optional
    comment) — once `score` is non-null the token is consumed.
    """

    client = models.ForeignKey(
        "Client", on_delete=models.CASCADE, related_name="nps_responses"
    )
    token = models.CharField(max_length=64, unique=True, default=_nps_token)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    quarter_label = models.CharField(max_length=12)  # e.g. "2026-Q2"
    sent_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]
        unique_together = ("client", "quarter_label")

    def __str__(self) -> str:
        return f"NPS {self.quarter_label} {self.client.name} ({self.score or 'pending'})"

    @property
    def category(self) -> str | None:
        if self.score is None:
            return None
        if self.score >= 9:
            return "promoter"
        if self.score >= 7:
            return "passive"
        return "detractor"


class Contact(models.Model):
    """A person at a client organization."""

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="contacts"
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self):
        return f"{self.name} ({self.client.name})"


class SystemType(models.TextChoices):
    NETWORK = "network", "Network"
    AUTOMATION = "automation", "Home Automation"
    WEBSITE = "website", "Website"
    APP = "app", "Mobile App"
    SECURITY = "security", "Security / CCTV"


class HealthStatus(models.TextChoices):
    UNKNOWN = "", "Unknown"
    OK = "ok", "OK"
    DEGRADED = "degraded", "Degraded"
    DOWN = "down", "Down"


class System(models.Model):
    """A piece of infrastructure / software belonging to a client."""

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="systems"
    )
    type = models.CharField(max_length=16, choices=SystemType.choices)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Free-form JSON for device inventory (UniFi APs, switches, NVR cameras, …)
    devices_json = models.JSONField(default=dict, blank=True)

    # Encrypted via Fernet — never expose raw via the API.
    credentials_encrypted = models.TextField(blank=True)

    monitoring_url = models.URLField(blank=True)
    installed_date = models.DateField(null=True, blank=True)

    # Populated by the periodic monitoring task (e.g. UniFi pull).
    last_checked_at = models.DateTimeField(null=True, blank=True)
    health_status = models.CharField(
        max_length=16, choices=HealthStatus.choices, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["client__name", "name"]

    def __str__(self):
        return f"{self.client.name} — {self.name}"

    # --- credential helpers -------------------------------------------
    def set_credentials(self, plaintext: str) -> None:
        self.credentials_encrypted = encrypt(plaintext)

    def get_credentials(self) -> str:
        return decrypt(self.credentials_encrypted)
