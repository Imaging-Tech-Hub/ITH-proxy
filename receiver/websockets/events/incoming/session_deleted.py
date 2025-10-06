"""
Session Deleted Event.
"""
from dataclasses import dataclass
from ..base import WebSocketEvent


@dataclass
class SessionDeletedEvent(WebSocketEvent):
    """
    Session deletion event.
    Notifies proxy to remove session from local PACS.

    Exact payload from docs:
    {
      "event_type": "session.deleted",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "session",
      "entity_id": "sess_def456",
      "payload": {
        "subject_id": "subj_ghi789",
        "session_label": "MRI-2025-001",
        "study_instance_uid": "1.2.840.113619.2.55.3.123456789.1234"
      }
    }

    Action Required:
    1. Remove session from local PACS database
    2. Remove all scans belonging to this session
    3. Update subject's session count
    4. Use study_instance_uid to identify the correct DICOM study
    """
    event_type: str = "session.deleted"
    entity_type: str = "session"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        session_id: str,
        subject_id: str,
        session_label: str,
        study_instance_uid: str
    ) -> 'SessionDeletedEvent':
        """Create session deleted event with exact payload structure from docs."""
        return cls(
            event_type="session.deleted",
            workspace_id=workspace_id,
            entity_type="session",
            entity_id=session_id,
            payload={
                "subject_id": subject_id,
                "session_label": session_label,
                "study_instance_uid": study_instance_uid
            }
        )
