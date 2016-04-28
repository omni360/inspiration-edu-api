from rest_framework import permissions


class ProjectAnalyticsPermission(permissions.BasePermission):
    """If the user has a owner/author allow view"""

    def has_object_permission(self, request, view, obj):
        return obj.is_editor(request.user)