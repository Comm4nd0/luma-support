"""Optional middleware: restrict /admin/ to a configured IP allowlist.

Set ``ADMIN_IP_ALLOWLIST`` in env (comma-separated) to enable.
Empty / unset = no enforcement, so existing deploys keep working without
any change. Logs and 403s on a mismatch — never raises.
"""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseForbidden


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AdminIpAllowlistMiddleware:
    """Block /admin/ requests from IPs outside ``ADMIN_IP_ALLOWLIST``.

    The /admin/ login form is the highest-blast-radius surface on the
    box; this turns it into a "VPN or office network only" door without
    needing a separate reverse-proxy rule.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowlist = [
            ip.strip()
            for ip in getattr(settings, "ADMIN_IP_ALLOWLIST", "").split(",")
            if ip.strip()
        ]
        if allowlist and request.path.startswith("/admin"):
            if _client_ip(request) not in allowlist:
                return HttpResponseForbidden(
                    "Admin access from this IP is not permitted."
                )
        return self.get_response(request)
