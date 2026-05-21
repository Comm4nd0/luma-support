"""Liveness + readiness probes."""
import redis
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health(_request):
    return JsonResponse({"status": "ok"})


def readyz(_request):
    """Readiness — verify DB and Redis are reachable."""
    checks = {"db": False, "redis": False}
    try:
        connections["default"].cursor().execute("SELECT 1")
        checks["db"] = True
    except OperationalError:
        pass

    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        r.ping()
        checks["redis"] = True
    except Exception:
        pass

    ok = all(checks.values())
    return JsonResponse({"status": "ready" if ok else "not_ready", "checks": checks},
                        status=200 if ok else 503)


def integrations(_request):
    """Per-integration health snapshot — returns plain JSON.

    Aimed at the staff dashboard tile and uptime-monitor checks. Returns
    200 even when some integrations are misconfigured — the per-row
    ``ok`` flag carries the state. The HTTP status would only flip
    on a 500 from the snapshot itself.
    """
    from .integrations_health import snapshot

    rows = snapshot()
    return JsonResponse(
        {
            "integrations": rows,
            "all_ok": all(r["ok"] for r in rows if r["configured"]),
        }
    )
