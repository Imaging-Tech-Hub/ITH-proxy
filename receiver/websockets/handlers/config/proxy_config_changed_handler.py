"""ProxyConfigChanged Handler."""
"""
Configuration Event Handlers.
Handle proxy configuration update events from backend.
"""
from typing import Dict, Any, List
from ..base import BaseEventHandler
from receiver.utils.config import NodeConfig


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
            await self._apply_configuration(new_config, changed_fields)

            self.logger.info(f"Successfully applied config changes: {', '.join(changed_fields)}")

        except Exception as e:
            self.logger.error(f"Error applying configuration: {e}", exc_info=True)

    async def _apply_configuration(self, config: Dict[str, Any], changed_fields: List[str]):
        """Apply configuration changes by reloading from API."""
        from asgiref.sync import sync_to_async
        from receiver.services.config import get_config_service

        for field in changed_fields:
            value = config.get(field)
            self.logger.info(f"Config changed: {field} = {value}")

        self.logger.info("Reloading configuration from API...")

        config_service = await sync_to_async(get_config_service, thread_sensitive=False)()

        if not config_service:
            self.logger.error("Config service not available")
            return

        config_data = await sync_to_async(config_service.fetch_configuration, thread_sensitive=False)()

        if config_data:
            await sync_to_async(config_service.save_configuration, thread_sensitive=False)(config_data)
            self.logger.info(" Configuration reloaded successfully")
        else:
            self.logger.error(" Failed to reload configuration")
