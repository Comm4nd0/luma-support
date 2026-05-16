"""UniFi Network controller integration.

Logs in to a UniFi controller, fetches device inventory, and returns a
normalised result. Designed against UniFi OS (modern controllers); the
classic /api/login path can be swapped in by tweaking `LOGIN_PATH`.

Credentials live in `clients.System.credentials_encrypted` as JSON:

    {"username": "admin", "password": "...", "site": "default"}

The controller URL goes in `System.monitoring_url`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

LOGIN_PATH = "/api/auth/login"
DEVICES_PATH_TEMPLATE = "/proxy/network/api/s/{site}/stat/device"

# UniFi state codes — 1 means actively connected. Other values cover
# upgrading / pending adoption / disconnected; we treat anything ≠ 1
# as not-online for health purposes.
STATE_CONNECTED = 1


@dataclass
class UnifiDevice:
    mac: str
    name: str
    model: str
    state: int
    ip: str
    last_seen: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiResult:
    devices: list[UnifiDevice]

    @property
    def online(self) -> int:
        return sum(1 for d in self.devices if d.state == STATE_CONNECTED)

    @property
    def offline(self) -> int:
        return len(self.devices) - self.online

    @property
    def total(self) -> int:
        return len(self.devices)


def fetch_devices(
    controller_url: str,
    username: str,
    password: str,
    site: str = "default",
    *,
    timeout: float = 10.0,
    verify_ssl: bool = False,
) -> UnifiResult:
    """Authenticate to `controller_url` and return its device inventory.

    Self-signed certs are common on UniFi appliances so SSL verification
    defaults to off. Callers can override for hosted controllers.
    Raises httpx.HTTPError on transport or auth failure.
    """
    base = controller_url.rstrip("/")
    with httpx.Client(base_url=base, verify=verify_ssl, timeout=timeout) as client:
        login = client.post(
            LOGIN_PATH, json={"username": username, "password": password}
        )
        login.raise_for_status()
        csrf = login.headers.get("x-csrf-token") or login.headers.get(
            "x-updated-csrf-token"
        )
        headers = {"x-csrf-token": csrf} if csrf else {}

        resp = client.get(
            DEVICES_PATH_TEMPLATE.format(site=site), headers=headers
        )
        resp.raise_for_status()
        payload = resp.json()

    devices = [
        UnifiDevice(
            mac=d.get("mac", ""),
            name=d.get("name") or d.get("model", "device"),
            model=d.get("model", ""),
            state=int(d.get("state", 0)),
            ip=d.get("ip", "") or "",
            last_seen=int(d.get("last_seen", 0) or 0),
            raw={
                k: d.get(k)
                for k in ("uptime", "version", "adopted", "site_id", "type")
                if k in d
            },
        )
        for d in payload.get("data", [])
    ]
    return UnifiResult(devices=devices)


def health_from(result: UnifiResult) -> str:
    """Bucket a UnifiResult into ok / degraded / down for `System.health_status`."""
    if result.total == 0:
        return "down"
    if result.online == 0:
        return "down"
    if result.offline == 0:
        return "ok"
    return "degraded"


def serialise(result: UnifiResult) -> dict[str, Any]:
    """Shape suitable for `System.devices_json` (JSON-safe)."""
    return {
        "online": result.online,
        "offline": result.offline,
        "total": result.total,
        "devices": [
            {
                "mac": d.mac,
                "name": d.name,
                "model": d.model,
                "state": d.state,
                "ip": d.ip,
                "last_seen": d.last_seen,
                **d.raw,
            }
            for d in result.devices
        ],
    }
