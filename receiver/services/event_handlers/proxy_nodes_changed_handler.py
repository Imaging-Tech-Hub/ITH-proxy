"""
Proxy Nodes Changed Event Handler.
Handles proxy.nodes_changed events from ITH backend.
"""
import logging
from typing import Dict, Any
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ProxyNodesChangedHandler:
    """
    Handles proxy.nodes_changed events.
    Reloads node configuration when changed from backend.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle proxy.nodes_changed event.

        Event structure:
        {
          "event_type": "proxy.nodes_changed",
          "workspace_id": "ws_abc123",
          "entity_type": "proxy",
          "entity_id": "proxy_mno345",
          "payload": {
            "nodes": [
              {
                "node_id": "node_1",
                "name": "Main PACS Server",
                "ae_title": "MAIN_PACS",
                "host": "10.0.1.100",
                "port": 11112
              }
            ],
            "changed_action": "updated"
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

            nodes = payload.get('nodes', [])
            changed_action = payload.get('changed_action', 'updated')

            logger.info("=" * 60)
            logger.info(f"🔧 PROXY NODES CHANGED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Proxy: {proxy_id}")
            logger.info(f"Action: {changed_action}")
            logger.info(f"Nodes Count: {len(nodes)}")
            logger.info("=" * 60)

            for node in nodes:
                node_name = node.get('name', 'Unknown')
                node_id = node.get('node_id', 'Unknown')
                logger.info(f"- {node_name} ({node_id})")

            success = await self._reload_nodes()

            if success:
                logger.info(f" Node configuration reloaded successfully")
                logger.info(f"Action: {changed_action}")
                logger.info(f"Nodes updated: {len(nodes)}")
                return True
            else:
                logger.error(f" Failed to reload node configuration")
                return False

        except Exception as e:
            logger.error(f" Error handling proxy.nodes_changed event: {e}", exc_info=True)
            return False

    async def _reload_nodes(self) -> bool:
        """
        Reload node configuration from backend.

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

                config_data = config_service.fetch_configuration()

                if config_data:
                    config_service.save_configuration(config_data)
                    logger.info("Node configuration fetched and saved")

                    nodes = config_service.load_nodes()
                    logger.info(f"Total nodes: {len(nodes)}")
                    active_count = sum(1 for n in nodes if n.is_active)
                    logger.info(f"Active nodes: {active_count}")

                    return True
                else:
                    logger.error("Failed to fetch configuration from API")
                    return False

            return await sync_to_async(_reload)()

        except Exception as e:
            logger.error(f"Error reloading nodes: {e}", exc_info=True)
            return False
