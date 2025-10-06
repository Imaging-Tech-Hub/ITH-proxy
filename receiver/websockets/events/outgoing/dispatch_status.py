"""
Dispatch Status Event - Update on dispatch operation progress.
"""
from dataclasses import dataclass
from typing import Optional
from ..base import WebSocketEvent


@dataclass
class DispatchStatusEvent(WebSocketEvent):
    """
    Dispatch status update event.
    Sent by proxy to inform backend about dispatch progress.

    Payload:
    {
      "event_type": "dispatch.status",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "session|scan|subject",
      "entity_id": "sess_def456",
      "payload": {
        "node_id": "node_1",
        "status": "downloading|completed|failed",
        "progress": 75,
        "files_sent": 120,
        "files_total": 150,
        "error": "optional error message"
      }
    }
    """
    event_type: str = "dispatch.status"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        node_id: str,
        status: str,
        correlation_id: Optional[str] = None,
        progress: int = 0,
        files_sent: int = 0,
        files_total: int = 0,
        error: Optional[str] = None
    ) -> 'DispatchStatusEvent':
        """
        Create dispatch status event.

        Args:
            workspace_id: Workspace ID
            entity_type: Type of entity (subject/session/scan)
            entity_id: Entity ID
            node_id: Target node ID
            status: Status (downloading, completed, failed)
            correlation_id: Original dispatch correlation ID
            progress: Progress percentage (0-100)
            files_sent: Number of files sent
            files_total: Total number of files
            error: Error message if status is failed
        """
        payload = {
            "node_id": node_id,
            "status": status,
            "progress": progress,
            "files_sent": files_sent,
            "files_total": files_total
        }

        if error:
            payload["error"] = error

        event = cls(
            event_type="dispatch.status",
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload
        )

        if correlation_id:
            event.correlation_id = correlation_id

        return event
