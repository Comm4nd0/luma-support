"""Re-encrypt every Fernet ciphertext with the current primary key.

Run this after prepending a new key to FERNET_KEYS so the old key can
be safely retired:

    FERNET_KEYS=NEW_KEY,OLD_KEY  python manage.py rotate_fernet_keys
    # then drop OLD_KEY from the env

Targets:
  - clients.System.credentials_encrypted
  - billing.XeroConnection.refresh_token_encrypted

Corrupted ciphertexts are reported on stderr and skipped — the command
never crashes mid-batch.
"""
from __future__ import annotations

from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand
from django.db import transaction

from clients.encryption import _cipher


class Command(BaseCommand):
    help = (
        "Re-encrypt System credentials and XeroConnection refresh tokens "
        "with the current primary FERNET key."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would change without writing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        from billing.models import XeroConnection
        from clients.models import System

        cipher = _cipher()

        def _rotate_one(row, field: str) -> bool:
            token = getattr(row, field) or ""
            if not token:
                return False
            try:
                new_token = cipher.rotate(token.encode()).decode()
            except InvalidToken:
                self.stderr.write(
                    f"  skipping {row.__class__.__name__}#{row.pk}.{field} "
                    f"— invalid token"
                )
                return False
            if dry_run:
                return True
            setattr(row, field, new_token)
            row.save(update_fields=[field])
            return True

        systems = 0
        xero = 0
        # MultiFernet.rotate always returns a fresh ciphertext, so we
        # don't bother dedup-checking. Run inside a transaction so a
        # mid-batch failure rolls back.
        with transaction.atomic():
            for s in System.objects.exclude(credentials_encrypted="").iterator():
                if _rotate_one(s, "credentials_encrypted"):
                    systems += 1
            for c in XeroConnection.objects.all():
                if _rotate_one(c, "refresh_token_encrypted"):
                    xero += 1

        verb = "Would re-encrypt" if dry_run else "Re-encrypted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {systems} System credential(s) and "
                f"{xero} XeroConnection refresh token(s)."
            )
        )
