"""Custom User model.

Email is the USERNAME_FIELD; the username column is dropped.
A `role` discriminator separates admins, engineers and client users.
"""
import hashlib
import secrets

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", User.Role.ENGINEER)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ENGINEER = "engineer", "Engineer"
        CLIENT = "client", "Client"

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.ENGINEER
    )
    phone = models.CharField(max_length=32, blank=True)

    # For client users: link back to a Client record. Engineers/admins leave it null.
    client = models.ForeignKey(
        "clients.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    # 2FA / TOTP: secret is Fernet-encrypted via clients.encryption so a
    # DB dump doesn't leak codes. totp_enabled gates the verify step.
    totp_secret_encrypted = models.TextField(blank=True)
    totp_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    # --- TOTP helpers --------------------------------------------------
    def set_totp_secret(self, plaintext: str) -> None:
        from clients.encryption import encrypt

        self.totp_secret_encrypted = encrypt(plaintext)

    def get_totp_secret(self) -> str:
        from clients.encryption import decrypt

        return decrypt(self.totp_secret_encrypted)

    # --- convenience predicates ---------------------------------------
    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_engineer(self) -> bool:
        return self.role in (self.Role.ADMIN, self.Role.ENGINEER)

    @property
    def is_client(self) -> bool:
        return self.role == self.Role.CLIENT

    @property
    def can_view_all(self) -> bool:
        """Staff (admin/engineer roles) and Django superusers see everything;
        client users are scoped to their own client's data."""
        return self.is_superuser or self.is_engineer


def _hash_recovery_code(plain: str) -> str:
    """Stable hash for matching at verify time. sha256 is sufficient — the
    codes are short-lived single-use values, not passwords."""
    return hashlib.sha256(plain.strip().upper().encode("utf-8")).hexdigest()


def generate_recovery_code() -> str:
    """Produce a human-typable 10-character code like ``WX9P-3K2L``."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


class RecoveryCode(models.Model):
    """One-shot recovery code for 2FA — exchangeable for a TOTP code.

    Plaintext is shown to the user once on creation; only the hash is
    stored. On successful use the row is marked ``used_at`` so the
    same code can't be replayed.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="recovery_codes",
    )
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "code_hash"], name="uniq_recovery_code_per_user"
            ),
        ]

    def __str__(self):
        state = "used" if self.used_at else "active"
        return f"recovery({state}) for {self.user_id}"

    @classmethod
    def regenerate_for(cls, user, count: int = 10) -> list[str]:
        """Replace any existing codes with ``count`` fresh ones.

        Returns the plaintexts (shown once to the user); only the hashes
        are written to the DB.
        """
        cls.objects.filter(user=user).delete()
        plains = []
        for _ in range(count):
            plain = generate_recovery_code()
            cls.objects.create(user=user, code_hash=_hash_recovery_code(plain))
            plains.append(plain)
        return plains

    @classmethod
    def consume(cls, user, plain: str) -> bool:
        """Mark a code used; returns True on a match, False otherwise."""
        from django.utils import timezone

        row = cls.objects.filter(
            user=user, code_hash=_hash_recovery_code(plain), used_at__isnull=True
        ).first()
        if row is None:
            return False
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        return True
