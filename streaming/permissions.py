"""Custom permission classes used by the API."""
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """Allow read-only requests for everyone but restrict writes to admins."""

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class HasActiveSubscription(BasePermission):
    """Only allow access to users with an active subscription."""

    message = "Your subscription is not active. Please renew your subscription first."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.active_subscription)

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)


class CanAccessVideo(BasePermission):
    """Ensure the requesting user can access the provided video object."""

    message = "You need a proper subscription to view this video."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not getattr(obj, "can_user_access", None):
            return True
        if request.method in SAFE_METHODS:
            return obj.can_user_access(user)
        return obj.can_user_access(user)
