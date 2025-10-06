"""
Subject Dispatch Event.
"""
from dataclasses import dataclass
from typing import List
from ..base import WebSocketEvent


@dataclass
class SubjectDispatchEvent(WebSocketEvent):
    """
    Subject dispatch event.
    Tells proxy to download subject to specified nodes.

    Exact payload from docs:
    {
      "event_type": "subject.dispatch",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "subject",
      "entity_id": "subj_ghi789",
      "payload": {
        "nodes": ["node_1", "node_2"],
        "subject_identifier": "PATIENT-001",
        "priority": "high"
      }
    }

    Priority Levels: low, normal, high, urgent

    Action Required:
    1. Check if any of the specified nodes are managed by this proxy
    2. For each matching node, download the subject using REST API:
       GET /proxy/{workspace_id}/subjects/{subject_id}/download
    3. Store DICOM files in the appropriate node storage
    """
    event_type: str = "subject.dispatch"
    entity_type: str = "subject"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        subject_id: str,
        nodes: List[str],
        subject_identifier: str,
        priority: str = "normal"
    ) -> 'SubjectDispatchEvent':
        """Create subject dispatch event with exact payload structure from docs."""
        return cls(
            event_type="subject.dispatch",
            workspace_id=workspace_id,
            entity_type="subject",
            entity_id=subject_id,
            payload={
                "nodes": nodes,
                "subject_identifier": subject_identifier,
                "priority": priority
            }
        )
