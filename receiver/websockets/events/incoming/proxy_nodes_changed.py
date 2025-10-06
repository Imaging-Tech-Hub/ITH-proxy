"""
Proxy Nodes Changed Event.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
from ..base import WebSocketEvent


@dataclass
class ProxyNodesChangedEvent(WebSocketEvent):
    """
    Proxy nodes changed event.
    Notifies proxy that its node configuration has changed.

    Exact payload from docs:
    {
      "event_type": "proxy.nodes_changed",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "proxy",
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
          },
          {
            "node_id": "node_2",
            "name": "Backup PACS",
            "ae_title": "BACKUP_PACS",
            "host": "10.0.1.101",
            "port": 11112,
            "storage_path": "/data/dicom/backup"
          }
        ],
        "changed_action": "updated"
      }
    }

    Changed Actions: added, removed, updated, replaced

    Action Required:
    1. Update local node configuration
    2. Reload PACS node settings
    3. Re-establish DICOM connections if needed
    """
    event_type: str = "proxy.nodes_changed"
    entity_type: str = "proxy"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        proxy_id: str,
        nodes: List[Dict[str, Any]],
        changed_action: str = "updated"
    ) -> 'ProxyNodesChangedEvent':
        """Create nodes changed event with exact payload structure from docs."""
        return cls(
            event_type="proxy.nodes_changed",
            workspace_id=workspace_id,
            entity_type="proxy",
            entity_id=proxy_id,
            payload={
                "nodes": nodes,
                "changed_action": changed_action
            }
        )
