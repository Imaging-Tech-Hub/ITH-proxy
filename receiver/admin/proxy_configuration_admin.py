"""
Admin interface for Proxy Configuration.
"""
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from receiver.models import ProxyConfiguration


@admin.register(ProxyConfiguration)
class ProxyConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for ProxyConfiguration singleton model.

    Features:
    - Read-only IP address (auto-detected)
    - Editable port and AE title
    - Editable resolver API URL
    - Shows current DICOM address
    - Prevents deletion
    - Prevents adding multiple instances
    """

    list_display = (
        'ae_title',
        'ip_address',
        'port',
        'dicom_address',
        'api_connection_status',
        'has_resolver',
        'updated_at'
    )

    fieldsets = (
        ('DICOM Configuration', {
            'fields': ('ip_address', 'port', 'ae_title'),
            'description': 'DICOM SCP server settings. Changes to port or AE title will restart the server.'
        }),
        ('Laminate API Configuration', {
            'fields': ('api_connection_status_detail',),
            'description': 'Proxy authentication is configured via PROXY_KEY environment variable.'
        }),
        ('Resolver API', {
            'fields': ('resolver_api_url',),
            'description': 'PHI Resolver API URL (optional)'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('ip_address', 'created_at', 'updated_at', 'api_connection_status_detail')

    def has_add_permission(self, request):
        """Only allow one instance."""
        return not ProxyConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of singleton instance."""
        return False

    actions = ['refresh_ip_address']

    @admin.action(description='Refresh IP address')
    def refresh_ip_address(self, request, queryset):
        """Refresh IP address for selected configuration."""
        for config in queryset:
            old_ip = config.ip_address
            new_ip = config.refresh_ip()

            if old_ip != new_ip:
                self.message_user(
                    request,
                    f"IP address updated: {old_ip} → {new_ip}",
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"IP address unchanged: {new_ip}",
                    messages.INFO
                )

    @admin.display(description='Has Resolver', boolean=True)
    def has_resolver(self, obj):
        """Show if resolver is configured."""
        return obj.has_resolver_configured()

    @admin.display(description='API Status')
    def api_connection_status(self, obj):
        """Show API connection status in list view."""
        from django.conf import settings

        proxy_key = getattr(settings, 'PROXY_KEY', '')
        if not proxy_key:
            return format_html('<span style="color: gray;">⚫ Not Configured</span>')

        try:
            from receiver.services.laminate_api_client import LaminateAPIClient

            api_url = getattr(settings, 'LAMINATE_API_URL', 'http://localhost:8000')
            client = LaminateAPIClient(api_url, proxy_key)
            config = client.get_proxy_configuration()

            if config:
                return format_html('<span style="color: green;">🟢 Connected</span>')
            else:
                return format_html('<span style="color: red;">🔴 Failed</span>')
        except Exception:
            return format_html('<span style="color: orange;">🟠 Unknown</span>')

    @admin.display(description='API Connection Status')
    def api_connection_status_detail(self, obj):
        """Show detailed API connection status in form view."""
        from django.conf import settings

        proxy_key = getattr(settings, 'PROXY_KEY', '')
        api_url = getattr(settings, 'LAMINATE_API_URL', 'http://localhost:8000')

        if not proxy_key:
            return format_html(
                '<div style="padding: 10px; background: #f8f9fa; border-left: 4px solid #6c757d;">'
                '<strong>Status:</strong> Not Configured<br>'
                '<small>Please set PROXY_KEY environment variable to connect to Laminate API.</small>'
                '</div>'
            )

        try:
            from receiver.services.laminate_api_client import LaminateAPIClient

            client = LaminateAPIClient(api_url, proxy_key)
            config = client.get_proxy_configuration()

            if config:
                workspace_id = config.get('workspace_id', 'Unknown')
                proxy_name = config.get('name', 'Unknown')
                return format_html(
                    '<div style="padding: 10px; background: #d4edda; border-left: 4px solid #28a745;">'
                    '<strong>Status:</strong> 🟢 Connected<br>'
                    '<strong>API URL:</strong> {}<br>'
                    '<strong>Workspace:</strong> {}<br>'
                    '<strong>Proxy Name:</strong> {}<br>'
                    '<small>Connection successful! Proxy key configured via environment.</small>'
                    '</div>',
                    api_url,
                    workspace_id,
                    proxy_name
                )
            else:
                return format_html(
                    '<div style="padding: 10px; background: #f8d7da; border-left: 4px solid #dc3545;">'
                    '<strong>Status:</strong> 🔴 Connection Failed<br>'
                    '<strong>API URL:</strong> {}<br>'
                    '<small>Unable to fetch configuration. Check your PROXY_KEY environment variable.</small>'
                    '</div>',
                    api_url
                )
        except Exception as e:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">'
                '<strong>Status:</strong> 🟠 Error<br>'
                '<strong>API URL:</strong> {}<br>'
                '<small>Error: {}</small>'
                '</div>',
                api_url,
                str(e)
            )

    @admin.display(description='Proxy Key')
    def proxy_key_display(self, obj):
        """Display proxy key with masking and edit option."""
        if not obj.proxy_key:
            return format_html(
                '<div style="margin-bottom: 10px;">'
                '<input type="text" name="proxy_key" id="id_proxy_key" maxlength="256" '
                'placeholder="Enter proxy key from Laminate dashboard" '
                'style="width: 100%; padding: 8px; font-family: monospace;">'
                '</div>'
            )

        masked = '•' * 40 + obj.proxy_key[-8:]

        return format_html(
            '<div style="margin-bottom: 10px;">'
            '<div id="proxy-key-masked" style="font-family: monospace; padding: 8px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; margin-bottom: 5px;">'
            '{}'
            '</div>'
            '<button type="button" onclick="editProxyKey()" style="padding: 5px 10px; cursor: pointer;">✏️ Edit</button>'
            '<div id="proxy-key-input" style="display: none; margin-top: 10px;">'
            '<input type="text" name="proxy_key" id="id_proxy_key" maxlength="256" value="{}" '
            'style="width: 100%; padding: 8px; font-family: monospace;">'
            '<br><small>Current key will be replaced when you save.</small>'
            '</div>'
            '<script>'
            'function toggleProxyKey() {{'
            '  var masked = document.getElementById("proxy-key-masked");'
            '  if (masked.textContent.includes("•")) {{'
            '    masked.textContent = "{}";'
            '  }} else {{'
            '    masked.textContent = "{}";'
            '  }}'
            '}}'
            'function editProxyKey() {{'
            '  document.getElementById("proxy-key-input").style.display = "block";'
            '}}'
            '</script>'
            '</div>',
            masked,
            obj.proxy_key,
            obj.proxy_key,
            masked
        )

    def save_model(self, request, obj, form, change):
        """Save model and show informative message."""
        super().save_model(request, obj, form, change)

        if 'port' in form.changed_data or 'ae_title' in form.changed_data:
            self.message_user(
                request,
                f"DICOM server will restart with new configuration: {obj.dicom_address}",
                messages.WARNING
            )

    change_form_template = None

    class Media:
        css = {
            'all': ()
        }
        js = ()
