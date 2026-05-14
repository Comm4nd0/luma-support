"""Admin-only gates for billing.

There is no admin gate in the portal otherwise — bare LoginRequiredMixin is
the existing baseline. Billing is the first feature restricted to
``user.role == 'admin'``.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from rest_framework.permissions import BasePermission


class AdminPortalMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = False

    def test_func(self) -> bool:
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "is_admin_role", False))

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect("portal:dashboard")


class IsAdmin(BasePermission):
    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "is_admin_role", False))
