"""ProxyStatusChanged Handler."""
"""
Configuration Event Handlers.
Handle proxy configuration update events from backend.
"""
from typing import Dict, Any, List
from ..base import BaseEventHandler
from receiver.utils.config import NodeConfig


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
