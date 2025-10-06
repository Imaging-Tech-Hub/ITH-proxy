"""
Proxy Configuration Model - Singleton pattern.
Stores editable proxy configuration that controls DICOM SCP server.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
import socket


class ProxyConfigurationManager(models.Manager):
    """Custom manager for ProxyConfiguration singleton."""

    def get_instance(self):
        """
        Get or create the singleton instance.

        Returns:
            ProxyConfiguration: The singleton instance
        """
        instance, created = self.get_or_create(pk=1)
        if created:
            instance.ip_address = self._get_server_ip()
            instance.save()
        return instance

    def _get_server_ip(self) -> str:
        """
        Auto-detect server IP address.

        Returns:
            str: Server IP address
        """
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            return ip_address
        except Exception:
            return '127.0.0.1'


class ProxyConfiguration(models.Model):
    """
    Proxy Configuration - Singleton model.

    Controls DICOM SCP server settings:
    - ip_address: Auto-detected server IP (read-only)
    - port: DICOM SCP port (editable, default: 11112)
    - ae_title: Application Entity Title (editable, max 16 chars)
    - resolver_api_url: PHI resolver API URL (editable)

    Note: Only one record is allowed (enforced via save() and manager)
    Changes to port or ae_title trigger DICOM server restart
    """

    ip_address = models.GenericIPAddressField(
        protocol='both',
        help_text="Server IP address (auto-detected)"
    )

    # Port (editable)
    port = models.PositiveIntegerField(
        default=11112,
        validators=[
            MinValueValidator(1024),
            MaxValueValidator(65535)
        ],
        help_text="DICOM SCP port (1024-65535)"
    )

    ae_title = models.CharField(
        max_length=16,
        default='LAMINATE_PROXY',
        help_text="Application Entity Title (max 16 characters)"
    )

    resolver_api_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text="PHI Resolver API URL (optional)"
    )

    proxy_key = models.CharField(
        max_length=256,
        blank=True,
        default='',
        help_text="Laminate API Proxy Key (from dashboard)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProxyConfigurationManager()

    class Meta:
        db_table = 'proxy_configuration'
        verbose_name = 'Proxy Configuration'
        verbose_name_plural = 'Proxy Configuration'

    def __str__(self):
        return f"Proxy Config: {self.ae_title}@{self.ip_address}:{self.port}"

    def save(self, *args, **kwargs):
        """
        Override save to enforce singleton pattern.
        Only allow one record (pk=1).
        Auto-update IP address on save.
        """
        self.pk = 1

        self.ip_address = self._get_server_ip()

        if len(self.ae_title) > 16:
            raise ValidationError('AE Title cannot exceed 16 characters')

        if not self.ae_title.replace('_', '').replace('-', '').isalnum():
            raise ValidationError('AE Title can only contain alphanumeric characters, dashes, and underscores')

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of the singleton instance."""
        raise ValidationError('Cannot delete proxy configuration. You can only modify it.')

    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance.

        Returns:
            ProxyConfiguration: The singleton instance
        """
        return cls.objects.get_instance()

    def _get_server_ip(self) -> str:
        """
        Auto-detect server IP address.

        Returns:
            str: Server IP address
        """
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            return ip_address
        except Exception:
            return '127.0.0.1'

    def refresh_ip(self) -> str:
        """
        Refresh IP address (in case server IP changed).

        Returns:
            str: New IP address
        """
        old_ip = self.ip_address
        new_ip = self._get_server_ip()

        if old_ip != new_ip:
            self.ip_address = new_ip
            self.save()

        return new_ip

    @property
    def dicom_address(self) -> str:
        """
        Get DICOM address in format: AE_TITLE@IP:PORT

        Returns:
            str: DICOM address
        """
        return f"{self.ae_title}@{self.ip_address}:{self.port}"

    def has_resolver_configured(self) -> bool:
        """
        Check if resolver API URL is configured.

        Returns:
            bool: True if resolver URL is set
        """
        return bool(self.resolver_api_url and self.resolver_api_url.strip())
