"""Per-System rotation status — used by the Fernet admin tile."""
from __future__ import annotations

from dataclasses import dataclass

from .encryption import encrypted_with_primary
from .models import System


@dataclass
class FernetStatus:
    total_with_creds: int
    on_primary: int
    on_old_key: int
    unreadable: int
    keys_configured: int

    @property
    def rotation_pct(self) -> int:
        if not self.total_with_creds:
            return 100
        return int(round(100 * self.on_primary / self.total_with_creds))

    @property
    def needs_rotation(self) -> bool:
        return self.on_old_key > 0 or self.unreadable > 0


def snapshot() -> FernetStatus:
    """Walk every System row that has a credential blob and bucket it.

    Constant-time per row (single Fernet decrypt attempt against the
    primary, one fall-back if needed). For Marco's installed base
    (~hundreds of systems) this is fine to compute on demand.
    """
    from .encryption import _keys

    total = on_primary = on_old = unreadable = 0
    qs = System.objects.exclude(credentials_encrypted="").values_list(
        "credentials_encrypted", flat=True
    )
    for token in qs:
        total += 1
        state = encrypted_with_primary(token)
        if state is True:
            on_primary += 1
        elif state is False:
            on_old += 1
        else:
            unreadable += 1
    return FernetStatus(
        total_with_creds=total,
        on_primary=on_primary,
        on_old_key=on_old,
        unreadable=unreadable,
        keys_configured=len(_keys()),
    )
