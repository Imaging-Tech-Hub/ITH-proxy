"""
Scan Dispatch Event.
"""
from dataclasses import dataclass
from typing import List
from ..base import WebSocketEvent


@dataclass
class ScanDispatchEvent(WebSocketEvent):
    """
    Scan dispatch event.
    Tells proxy to download scan to specified nodes.

    Exact payload from docs:
    {
      "event_type": "scan.dispatch",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "scan",
      "entity_id": "scan_jkl012",
      "payload": {
        "subject_id": "subj_ghi789",
        "session_id": "sess_def456",
        "nodes": ["node_3"],
        "scan_number": 3,
        "modality": "MR",
        "priority": "urgent"
      }
    }

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the scan using REST API:
       GET /proxy/{workspace_id}/scans/{scan_id}/download?subject_id={subject_id}&session_id={session_id}
    """
    event_type: str = "scan.dispatch"
    entity_type: str = "scan"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        scan_id: str,
        subject_id: str,
        session_id: str,
        nodes: List[str],
        scan_number: int,
        modality: str,
        priority: str = "normal"
    ) -> 'ScanDispatchEvent':
        """Create scan dispatch event with exact payload structure from docs."""
        return cls(
            event_type="scan.dispatch",
            workspace_id=workspace_id,
            entity_type="scan",
            entity_id=scan_id,
            payload={
                "subject_id": subject_id,
                "session_id": session_id,
                "nodes": nodes,
                "scan_number": scan_number,
                "modality": modality,
                "priority": priority
            }
        )
