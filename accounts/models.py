"""Custom User model.

Email is the USERNAME_FIELD; the username column is dropped.
A `role` discriminator separates admins, engineers and client users.
"""
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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

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
