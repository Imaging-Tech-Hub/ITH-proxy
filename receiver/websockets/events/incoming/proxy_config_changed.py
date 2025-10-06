"""
Proxy Config Changed Event.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
from ..base import WebSocketEvent


@dataclass
class ProxyConfigChangedEvent(WebSocketEvent):
    """
    Proxy configuration changed event.
    Notifies proxy of configuration updates.

    Exact payload from docs:
    {
      "event_type": "proxy.config_changed",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
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

    Action Required:
    1. Apply new configuration values
    2. Reload affected components
    3. Log configuration change
    """
    event_type: str = "proxy.config_changed"
    entity_type: str = "proxy"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        proxy_id: str,
        changed_fields: List[str],
        new_config: Dict[str, Any]
    ) -> 'ProxyConfigChangedEvent':
        """Create config changed event with exact payload structure from docs."""
        return cls(
            event_type="proxy.config_changed",
            workspace_id=workspace_id,
            entity_type="proxy",
            entity_id=proxy_id,
            payload={
                "changed_fields": changed_fields,
                "new_config": new_config
            }
        )
