"""
Proxy Config Changed Event Handler.
Handles proxy.config_changed events from Laminate backend.
"""
import logging
from typing import Dict, Any
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ProxyConfigChangedHandler:
    """
    Handles proxy.config_changed events.
    Reloads proxy configuration when changed from backend.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle proxy.config_changed event.

        Event structure:
        {
          "event_type": "proxy.config_changed",
          "workspace_id": "ws_abc123",
          "entity_type": "proxy",
          "entity_id": "proxy_mno345",
          "payload": {
            "changed_fields": ["retry_count", "timeout"],
            "new_config": {
              "retry_count": 5,
              "timeout": 30
            }
          }
        }

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            proxy_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})

            changed_fields = payload.get('changed_fields', [])
            new_config = payload.get('new_config', {})

            logger.info("=" * 60)
            logger.info(f"PROXY CONFIG CHANGED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Proxy: {proxy_id}")
            logger.info(f"Changed Fields: {', '.join(changed_fields)}")
            logger.info("=" * 60)

            if not changed_fields:
                logger.warning(f"No fields changed in config update")
                return True

            success = await self._reload_configuration()

            if success:
                logger.info(f" Configuration reloaded successfully")
                logger.info(f"Updated fields: {', '.join(changed_fields)}")
                for field in changed_fields:
                    if field in new_config:
                        logger.info(f"{field}: {new_config[field]}")
                return True
            else:
                logger.error(f" Failed to reload configuration")
                return False

        except Exception as e:
            logger.error(f" Error handling proxy.config_changed event: {e}", exc_info=True)
            return False

    async def _reload_configuration(self) -> bool:
        """
        Reload proxy configuration from backend.

        Returns:
            bool: True if reload successful
        """
        try:
            from receiver.services.proxy_config_service import get_config_service

            def _reload():
                config_service = get_config_service()
                if not config_service:
                    logger.error("Config service not available")
                    return False

                success = config_service.fetch_and_save_configuration()

                if success:
                    logger.info(" Configuration fetched and saved")
                    return True
                else:
                    logger.error(" Failed to fetch configuration from API")
                    return False

            return await sync_to_async(_reload)()

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}", exc_info=True)
            return False
