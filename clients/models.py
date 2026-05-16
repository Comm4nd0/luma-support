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
        max_length=16, choices=CarePlanTier.choices, default=CarePlanTier.NONE
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

    notes = models.TextField(blank=True)

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
