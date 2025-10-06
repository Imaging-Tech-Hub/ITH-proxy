"""
Proxy Status Changed Event.
"""
from dataclasses import dataclass
from ..base import WebSocketEvent


@dataclass
class ProxyStatusChangedEvent(WebSocketEvent):
    """
    Proxy status changed event.
    Notifies proxy of status changes (active/inactive/maintenance).

    Exact payload from docs:
    {
      "event_type": "proxy.status_changed",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "proxy",
      "entity_id": "proxy_mno345",
      "payload": {
        "new_status": "maintenance",
        "is_active": false,
        "reason": "Scheduled maintenance window"
      }
    }

    Status Values: active, inactive, maintenance, error

    Action Required:
    1. Update operational status
    2. If is_active: false, pause all operations
    3. If is_active: true, resume normal operations
    """
    event_type: str = "proxy.status_changed"
    entity_type: str = "proxy"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        proxy_id: str,
        new_status: str,
        is_active: bool,
        reason: str = ""
    ) -> 'ProxyStatusChangedEvent':
        """Create status changed event with exact payload structure from docs."""
        return cls(
            event_type="proxy.status_changed",
            workspace_id=workspace_id,
            entity_type="proxy",
            entity_id=proxy_id,
            payload={
                "new_status": new_status,
                "is_active": is_active,
                "reason": reason
            }
        )
