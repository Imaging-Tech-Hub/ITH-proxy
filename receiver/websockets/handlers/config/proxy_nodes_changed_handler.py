"""ProxyNodesChanged Handler."""
"""
Configuration Event Handlers.
Handle proxy configuration update events from backend.
"""
from typing import Dict, Any, List
from ..base import BaseEventHandler
from receiver.utils.config import NodeConfig


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
            nodes = [NodeConfig.from_dict(node_data) for node_data in nodes_data]

            await self._save_node_configuration(nodes, changed_action)

            self.logger.info(f"Successfully updated {len(nodes)} nodes (action: {changed_action})")

        except Exception as e:
            self.logger.error(f"Error updating nodes configuration: {e}", exc_info=True)

    async def _save_node_configuration(self, nodes: List[NodeConfig], action: str):
        """Reload node configuration from API."""
        from asgiref.sync import sync_to_async
        from receiver.services.config import get_config_service

        self.logger.info(f" Reloading node configuration from API (action: {action})...")

        config_service = await sync_to_async(get_config_service, thread_sensitive=False)()

        if not config_service:
            self.logger.error("Config service not available")
            return

        config_data = await sync_to_async(config_service.fetch_configuration, thread_sensitive=False)()

        if config_data:
            await sync_to_async(config_service.save_configuration, thread_sensitive=False)(config_data)
            self.logger.info(" Node configuration reloaded successfully from API")
        else:
            self.logger.error(" Failed to reload node configuration from API")
