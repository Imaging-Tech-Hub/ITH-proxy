"""
Configuration Event Handlers.
Handle proxy configuration update events from backend.
"""
from typing import Dict, Any, List
from .base import BaseEventHandler
from receiver.utils.node_config import NodeConfig


class ProxyNodesChangedHandler(BaseEventHandler):
    """
    Handle proxy.nodes_changed events.

    Action Required:
    1. Update local node configuration
    2. Reload PACS node settings
    3. Re-establish DICOM connections if needed
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle proxy nodes changed event.

        Payload:
        {
          "entity_id": "proxy_mno345",
          "payload": {
            "nodes": [
              {
                "node_id": "node_1",
                "name": "Main PACS Server",
                "ae_title": "MAIN_PACS",
                "host": "10.0.1.100",
                "port": 11112,
                "storage_path": "/data/dicom/main"
              }
            ],
            "changed_action": "updated"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})

        nodes_data = payload.get('nodes', [])
        changed_action = payload.get('changed_action', 'updated')

        self.logger.info(f"Handling proxy nodes changed: {changed_action} ({len(nodes_data)} nodes)")

        try:
            # Convert node dictionaries to NodeConfig objects
            nodes = [NodeConfig.from_dict(node_data) for node_data in nodes_data]

            # Save nodes to configuration
            await self._save_node_configuration(nodes, changed_action)

            self.logger.info(f"Successfully updated {len(nodes)} nodes (action: {changed_action})")

        except Exception as e:
            self.logger.error(f"Error updating nodes configuration: {e}", exc_info=True)

    async def _save_node_configuration(self, nodes: List[NodeConfig], action: str):
        """Reload node configuration from API."""
        from asgiref.sync import sync_to_async
        from receiver.services.proxy_config_service import get_config_service

        self.logger.info(f"🔄 Reloading node configuration from API (action: {action})...")

        # Get config service and reload (use sync_to_async with thread_sensitive=False)
        config_service = await sync_to_async(get_config_service, thread_sensitive=False)()

        if not config_service:
            self.logger.error("Config service not available")
            return

        # Fetch configuration from API
        config_data = await sync_to_async(config_service.fetch_configuration, thread_sensitive=False)()

        if config_data:
            # Save to memory
            await sync_to_async(config_service.save_configuration, thread_sensitive=False)(config_data)
            self.logger.info("✅ Node configuration reloaded successfully from API")
        else:
            self.logger.error("❌ Failed to reload node configuration from API")


class ProxyConfigChangedHandler(BaseEventHandler):
    """
    Handle proxy.config_changed events.

    Action Required:
    1. Apply new configuration values
    2. Reload affected components
    3. Log configuration change
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle proxy config changed event.

        Payload:
        {
          "entity_id": "proxy_mno345",
          "payload": {
            "changed_fields": ["retry_count", "timeout"],
            "new_config": {
              "retry_count": 5,
              "timeout": 30
            }
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})

        changed_fields = payload.get('changed_fields', [])
        new_config = payload.get('config', {})

        self.logger.info(f"Handling proxy config changed: {changed_fields}")

        try:
            # Apply configuration changes
            await self._apply_configuration(new_config, changed_fields)

            self.logger.info(f"Successfully applied config changes: {', '.join(changed_fields)}")

        except Exception as e:
            self.logger.error(f"Error applying configuration: {e}", exc_info=True)

    async def _apply_configuration(self, config: Dict[str, Any], changed_fields: List[str]):
        """Apply configuration changes by reloading from API."""
        from asgiref.sync import sync_to_async
        from receiver.services.proxy_config_service import get_config_service

        # Log changes
        for field in changed_fields:
            value = config.get(field)
            self.logger.info(f"Config changed: {field} = {value}")

        self.logger.info("🔄 Reloading configuration from API...")

        # Get config service and reload (use sync_to_async with thread_sensitive=False)
        config_service = await sync_to_async(get_config_service, thread_sensitive=False)()

        if not config_service:
            self.logger.error("Config service not available")
            return

        # Fetch configuration from API
        config_data = await sync_to_async(config_service.fetch_configuration, thread_sensitive=False)()

        if config_data:
            # Save to memory
            await sync_to_async(config_service.save_configuration, thread_sensitive=False)(config_data)
            self.logger.info("✅ Configuration reloaded successfully")
        else:
            self.logger.error("❌ Failed to reload configuration")


class ProxyStatusChangedHandler(BaseEventHandler):
    """
    Handle proxy.status_changed events.

    Action Required:
    1. Update operational status
    2. If is_active: false, pause all operations
    3. If is_active: true, resume normal operations
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle proxy status changed event.

        Payload:
        {
          "entity_id": "proxy_mno345",
          "payload": {
            "new_status": "maintenance",
            "is_active": false,
            "reason": "Scheduled maintenance window"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})

        new_status = payload.get('new_status')
        is_active = payload.get('is_active')
        reason = payload.get('reason', '')

        self.logger.info(f"Handling proxy status changed: {new_status} (active: {is_active})")
        if reason:
            self.logger.info(f"Reason: {reason}")

        try:
            await self._update_proxy_status(new_status, is_active, reason)

            if not is_active:
                self.logger.warning(f"Proxy set to inactive - Status: {new_status}, Reason: {reason}")
                self.logger.warning("All new DICOM associations will be rejected by access control")
            else:
                self.logger.info(f"Proxy set to active - Status: {new_status}")
                self.logger.info("DICOM associations will be accepted per access control rules")

        except Exception as e:
            self.logger.error(f"Error updating proxy status: {e}", exc_info=True)

    async def _update_proxy_status(self, status: str, is_active: bool, reason: str):
        """Update proxy status in configuration."""
        import json
        from pathlib import Path
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _update():
            from django.conf import settings

            config_dir = Path(settings.PROXY_CONFIG_DIR)
            status_file = config_dir / "status.json"

            status_data = {
                "status": status,
                "is_active": is_active,
                "reason": reason,
                "updated_at": self._get_timestamp()
            }

            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2)

        await _update()

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat() + 'Z'
