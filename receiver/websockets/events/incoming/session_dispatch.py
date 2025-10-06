"""
Session Dispatch Event.
"""
from dataclasses import dataclass
from typing import List
from ..base import WebSocketEvent


@dataclass
class SessionDispatchEvent(WebSocketEvent):
    """
    Session dispatch event.
    Tells proxy to download session to specified nodes.

    Exact payload from docs:
    {
      "event_type": "session.dispatch",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "session",
      "entity_id": "sess_def456",
      "payload": {
        "subject_id": "subj_ghi789",
        "nodes": ["node_1"],
        "session_label": "MRI-2025-001",
        "priority": "normal"
      }
    }

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the session using REST API:
       GET /proxy/{workspace_id}/sessions/{session_id}/download?subject_id={subject_id}
    """
    event_type: str = "session.dispatch"
    entity_type: str = "session"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        session_id: str,
        subject_id: str,
        nodes: List[str],
        session_label: str,
        priority: str = "normal"
    ) -> 'SessionDispatchEvent':
        """Create session dispatch event with exact payload structure from docs."""
        return cls(
            event_type="session.dispatch",
            workspace_id=workspace_id,
            entity_type="session",
            entity_id=session_id,
            payload={
                "subject_id": subject_id,
                "nodes": nodes,
                "session_label": session_label,
                "priority": priority
            }
        )
