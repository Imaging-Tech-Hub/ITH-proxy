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

        Args:
            token: JWT access token

        Returns:
            User information dict if valid, None otherwise
        """
        backend_url = getattr(settings, 'ITH_URL', 'http://localhost:8000')
        validate_endpoint = f"{backend_url}/api/v1/auth/tokens/validate"

        try:
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                validate_endpoint,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                user_info = {
                    'user_id': data.get('user', {}).get('id'),
                    'username': data.get('user', {}).get('username'),
                    'email': data.get('user', {}).get('email'),
                    'role': data.get('user', {}).get('role'),
                    'is_superuser': data.get('user', {}).get('is_superuser', False),
                    'session_id': data.get('session', {}).get('id'),
                    'workspace_id': data.get('user', {}).get('workspace_id'),
                }

                logger.debug(f"Token validated for user: {user_info.get('username')}")
                return user_info

            elif response.status_code == 401:
                logger.warning("Token validation failed: Unauthorized")
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
