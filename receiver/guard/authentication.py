"""
Authentication backends for Proxy REST API.
Validates JWT tokens against the ITH backend API.
"""
import logging
import requests
from typing import Optional, Tuple
from django.conf import settings
from rest_framework import authentication
from rest_framework import exceptions

logger = logging.getLogger('receiver.auth')


class BackendTokenAuthentication(authentication.BaseAuthentication):
    """
    Authentication class that validates JWT tokens against the ITH backend.

    Extracts the Bearer token from the Authorization header and validates it
    against the backend's /api/v1/auth/tokens/validate endpoint.
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        """
        Authenticate the request using the Bearer token.

        Args:
            request: Django request object

        Returns:
            Tuple of (user_info, token) if authenticated, None otherwise

        Raises:
            AuthenticationFailed: If token is invalid or validation fails
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) == 0:
            return None

        if parts[0].lower() != self.keyword.lower():
            return None

        if len(parts) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')

        if len(parts) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        token = parts[1]

        user_info = self.validate_token(token)

        if not user_info:
            raise exceptions.AuthenticationFailed('Invalid or expired token.')


        return (user_info, token)

    def validate_token(self, token: str) -> Optional[dict]:
        """
        Validate token against the ITH backend API.

        Uses GET /workspaces/{workspace_id}/proxies/{proxy_id} endpoint which:
        1. Validates the token
        2. Validates user has access to this specific proxy
        3. Returns proxy information if authorized

        Args:
            token: JWT access token

        Returns:
            User information dict if valid, None otherwise
        """
        # Get workspace_id and proxy_id from WebSocket client or config service
        try:
            from receiver.services.api import get_websocket_client
            from receiver.services.config import get_config_service

            ws_client = get_websocket_client()
            config_service = get_config_service()

            # Try to get IDs from WebSocket client first
            workspace_id = ws_client.workspace_id if ws_client else None
            proxy_id = ws_client.proxy_id if ws_client else None

            # Fallback to config service if WebSocket not connected yet
            if not workspace_id and config_service:
                workspace_id = config_service.get_workspace_id()
                proxy_id = config_service.get_proxy_id()

            if not workspace_id or not proxy_id:
                logger.warning("workspace_id or proxy_id not available - cannot validate token")
                raise exceptions.AuthenticationFailed('Proxy not initialized.')

        except Exception as e:
            logger.error(f"Error getting workspace/proxy IDs: {e}", exc_info=True)
            raise exceptions.AuthenticationFailed('Proxy configuration error.')

        backend_url = getattr(settings, 'ITH_URL', 'http://localhost:8000')
        validate_endpoint = f"{backend_url}/api/v1/workspaces/{workspace_id}/proxies/{proxy_id}"

        try:
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            }

            # Request with include_user_info=true to get user details if available
            params = {
                'include_user_info': 'true'
            }

            response = requests.get(
                validate_endpoint,
                headers=headers,
                params=params,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                # Extract user info from audit.created_by (when include_user_info=true)
                audit_data = data.get('audit', {})
                created_by = audit_data.get('created_by')

                # If created_by is a dict (user info included), extract from it
                if isinstance(created_by, dict):
                    user_id = created_by.get('id', 'unknown')
                    username = created_by.get('username', 'authenticated_user')
                    email = created_by.get('email')
                    role = created_by.get('role', 'user')
                    is_superuser = role == 'superuser'  # Backend uses 'superuser' role
                    first_name = created_by.get('first_name', '')
                    last_name = created_by.get('last_name', '')
                    full_name = created_by.get('full_name') or f"{first_name} {last_name}".strip()
                else:
                    # Fallback if user info not included (should not happen with include_user_info=true)
                    user_id = created_by if isinstance(created_by, str) else 'unknown'
                    username = 'authenticated_user'
                    email = None
                    role = 'user'
                    is_superuser = False
                    full_name = 'Unknown User'

                user_info = {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'role': role,
                    'is_superuser': is_superuser,
                    'full_name': full_name,
                    'session_id': None,
                    'workspace_id': workspace_id,
                    'proxy_id': proxy_id,
                    'is_authenticated': True,
                }

                logger.debug(f"Token validated for user {username} ({full_name}, role: {role}) - workspace: {workspace_id}, proxy: {proxy_id}")
                return user_info

            elif response.status_code == 401:
                logger.warning("Token validation failed: Unauthorized")
                return None

            elif response.status_code == 403:
                logger.warning("Token validation failed: Forbidden - user doesn't have access to this proxy")
                return None

            elif response.status_code == 404:
                logger.warning("Token validation failed: Proxy not found")
                return None

            else:
                logger.error(f"Token validation error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error("Token validation timeout - backend API not responding")
            raise exceptions.AuthenticationFailed('Authentication service unavailable.')

        except requests.exceptions.RequestException as e:
            logger.error(f"Token validation request failed: {e}")
            raise exceptions.AuthenticationFailed('Authentication service error.')

        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
            raise exceptions.AuthenticationFailed('Authentication error.')

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 Unauthenticated response.
        """
        return self.keyword


class ProxyUser:
    """
    Simple user object to hold authenticated user information.
    Compatible with DRF's request.user interface.
    """

    def __init__(self, user_info: dict):
        self.id = user_info.get('user_id')
        self.username = user_info.get('username')
        self.email = user_info.get('email')
        self.role = user_info.get('role')
        self.is_superuser = user_info.get('is_superuser', False)
        self.is_authenticated = True
        self.is_active = True
        self.workspace_id = user_info.get('workspace_id')
        self.session_id = user_info.get('session_id')

    def __str__(self):
        return f"{self.username} ({self.role})"

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission."""
        return self.is_superuser

    def has_module_perms(self, app_label):
        """Check if user has permissions for an app."""
        return self.is_superuser
