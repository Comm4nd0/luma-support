"""Client and System models."""
from django.db import models

from .encryption import decrypt, encrypt


class CarePlanTier(models.TextChoices):
    NONE = "none", "None"
    ESSENTIAL = "essential", "Essential"
    PROFESSIONAL = "professional", "Professional"
    ENTERPRISE = "enterprise", "Enterprise"


class Client(models.Model):
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    care_plan_tier = models.CharField(
        max_length=16, choices=CarePlanTier.choices, default=CarePlanTier.NONE
    )
    care_plan_start = models.DateField(null=True, blank=True)
    care_plan_renewal = models.DateField(null=True, blank=True)

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


class SystemType(models.TextChoices):
    NETWORK = "network", "Network"
    AUTOMATION = "automation", "Home Automation"
    WEBSITE = "website", "Website"
    APP = "app", "Mobile App"
    SECURITY = "security", "Security / CCTV"


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
