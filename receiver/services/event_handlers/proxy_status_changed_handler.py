"""
Proxy Status Changed Event Handler.
Handles proxy.status_changed events from ITH backend.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ProxyStatusChangedHandler:
    """
    Handles proxy.status_changed events.
    Updates proxy operational status based on backend changes.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle proxy.status_changed event.

        Event structure:
        {
          "event_type": "proxy.status_changed",
          "workspace_id": "ws_abc123",
          "entity_type": "proxy",
          "entity_id": "proxy_mno345",
          "payload": {
            "new_status": "maintenance",
            "is_active": false,
            "reason": "Scheduled maintenance window"
          }
        }

        Status Values: active, inactive, maintenance, error

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            proxy_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})

            new_status = payload.get('status') or payload.get('new_status', 'unknown')
            is_active = payload.get('is_active', True)
            reason = payload.get('reason', '')

            logger.info("=" * 60)
            logger.info(f" PROXY STATUS CHANGED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Proxy: {proxy_id}")
            logger.info(f"New Status: {new_status}")
            logger.info(f"Is Active: {is_active}")
            if reason:
                logger.info(f"Reason: {reason}")
            logger.info("=" * 60)

            if not is_active:
                logger.warning(f"Proxy marked as INACTIVE - operations may be paused")
                logger.warning(f"Reason: {reason or 'Not specified'}")

            else:
                logger.info(" Proxy marked as ACTIVE - normal operations")


            return True

        except Exception as e:
            logger.error(f" Error handling proxy.status_changed event: {e}", exc_info=True)
            return False
