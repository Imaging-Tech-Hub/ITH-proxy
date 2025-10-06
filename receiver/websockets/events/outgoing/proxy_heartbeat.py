"""
Proxy Heartbeat Event - Proxy health status update.
"""
from dataclasses import dataclass
from typing import Dict, Any
from ..base import WebSocketEvent


@dataclass
class ProxyHeartbeatEvent(WebSocketEvent):
    """
    Proxy heartbeat event.
    Sent periodically to inform backend about proxy health and status.

    Payload:
    {
      "event_type": "proxy.heartbeat",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "proxy",
      "entity_id": "proxy_mno345",
      "payload": {
        "status": "active",
        "nodes_online": 2,
        "nodes_total": 3,
        "active_dispatches": 5,
        "disk_usage_gb": 250.5,
        "version": "1.0.0"
      }
    }
    """
    event_type: str = "proxy.heartbeat"
    entity_type: str = "proxy"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        proxy_id: str,
        status: str,
        nodes_online: int,
        nodes_total: int,
        active_dispatches: int = 0,
        disk_usage_gb: float = 0.0,
        version: str = "1.0.0",
        **extra_info: Any
    ) -> 'ProxyHeartbeatEvent':
        """
        Create proxy heartbeat event.

        Args:
            workspace_id: Workspace ID
            proxy_id: Proxy ID
            status: Proxy status (active, inactive, error)
            nodes_online: Number of nodes currently online
            nodes_total: Total number of configured nodes
            active_dispatches: Number of active dispatch operations
            disk_usage_gb: Disk usage in GB
            version: Proxy software version
            **extra_info: Additional information to include
        """
        payload = {
            "status": status,
            "nodes_online": nodes_online,
            "nodes_total": nodes_total,
            "active_dispatches": active_dispatches,
            "disk_usage_gb": disk_usage_gb,
            "version": version
        }

        # Add any extra info
        payload.update(extra_info)

        return cls(
            event_type="proxy.heartbeat",
            workspace_id=workspace_id,
            entity_type="proxy",
            entity_id=proxy_id,
            payload=payload
        )
