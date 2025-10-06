"""
Custom permission classes for Proxy REST API.
"""
from rest_framework import permissions


class IsAuthenticated(permissions.BasePermission):
    """
    Permission that requires the user to be authenticated via backend token.
    """

    def has_permission(self, request, view):
        """Check if user is authenticated."""
        return request.user and getattr(request.user, 'is_authenticated', False)


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Permission that allows authenticated users full access,
    and unauthenticated users read-only access.
    """

    def has_permission(self, request, view):
        """Check permissions based on HTTP method."""
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and getattr(request.user, 'is_authenticated', False)


class IsSuperuser(permissions.BasePermission):
    """
    Permission that requires the user to be a superuser.
    """

    def has_permission(self, request, view):
        """Check if user is superuser."""
        return (
            request.user and
            getattr(request.user, 'is_authenticated', False) and
            getattr(request.user, 'is_superuser', False)
        )


class HasWorkspaceAccess(permissions.BasePermission):
    """
    Permission that checks if user has access to the requested workspace.
    """

    def has_permission(self, request, view):
        """Check if user has workspace access."""
        if not request.user or not getattr(request.user, 'is_authenticated', False):
            return False

        if getattr(request.user, 'is_superuser', False):
            return True


        requested_workspace = (
            view.kwargs.get('workspace_id') or
            request.query_params.get('workspace_id') or
            request.data.get('workspace_id')
        )

        if not requested_workspace:
            return True

        user_workspace = getattr(request.user, 'workspace_id', None)
        return user_workspace == requested_workspace


class CanManageNodes(permissions.BasePermission):
    """
    Permission for managing PACS nodes.
    Requires authentication and appropriate role.
    """

    def has_permission(self, request, view):
        """Check if user can manage nodes."""
        if not request.user or not getattr(request.user, 'is_authenticated', False):
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        user_role = getattr(request.user, 'role', '').lower()
        is_superuser = getattr(request.user, 'is_superuser', False)

        return is_superuser or user_role in ['admin', 'workspace_admin']


class CanViewDicomData(permissions.BasePermission):
    """
    Permission for viewing DICOM data.
    """

    def has_permission(self, request, view):
        """Check if user can view DICOM data."""
        if not request.user or not getattr(request.user, 'is_authenticated', False):
            return False

        return True


class CanDispatchDicom(permissions.BasePermission):
    """
    Permission for dispatching DICOM studies to nodes.
    """

    def has_permission(self, request, view):
        """Check if user can dispatch DICOM."""
        if not request.user or not getattr(request.user, 'is_authenticated', False):
            return False

        user_role = getattr(request.user, 'role', '').lower()
        is_superuser = getattr(request.user, 'is_superuser', False)

        return is_superuser or user_role in ['admin', 'workspace_admin', 'operator']
