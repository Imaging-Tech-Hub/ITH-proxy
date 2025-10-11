"""
Guard Module - Authentication and Authorization

Handles JWT authentication and permission checking for API endpoints.
"""
from .authentication import BackendTokenAuthentication, ProxyUser
from .permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
    IsSuperuser,
    HasWorkspaceAccess,
    CanManageNodes,
    CanViewDicomData,
    CanDispatchDicom,
)

__all__ = [
    # Authentication
    'BackendTokenAuthentication',
    'ProxyUser',
    # Permissions
    'IsAuthenticated',
    'IsAuthenticatedOrReadOnly',
    'IsSuperuser',
    'HasWorkspaceAccess',
    'CanManageNodes',
    'CanViewDicomData',
    'CanDispatchDicom',
]
