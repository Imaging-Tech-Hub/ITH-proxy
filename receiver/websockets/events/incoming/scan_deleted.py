"""
Scan Deleted Event.
"""
from dataclasses import dataclass
from ..base import WebSocketEvent


@dataclass
class ScanDeletedEvent(WebSocketEvent):
    """
    Scan deletion event.
    Notifies proxy to remove scan from local PACS.

    Exact payload from docs:
    {
      "event_type": "scan.deleted",
      "workspace_id": "ws_abc123",
      "timestamp": "2025-10-04T10:30:00.000Z",
      "correlation_id": "corr_xyz789",
      "entity_type": "scan",
      "entity_id": "scan_jkl012",
      "payload": {
        "subject_id": "subj_ghi789",
        "session_id": "sess_def456",
        "scan_number": 3,
        "study_instance_uid": "1.2.840.113619.2.55.3.123456789.1234"
      }
    }

    Action Required:
    1. Remove scan from local PACS database
    2. Update session's scan count
    3. Use study_instance_uid to identify the correct DICOM study
    """
    event_type: str = "scan.deleted"
    entity_type: str = "scan"

    @classmethod
    def create(
        cls,
        workspace_id: str,
        scan_id: str,
        subject_id: str,
        session_id: str,
        scan_number: int,
        study_instance_uid: str
    ) -> 'ScanDeletedEvent':
        """Create scan deleted event with exact payload structure from docs."""
        return cls(
            event_type="scan.deleted",
            workspace_id=workspace_id,
            entity_type="scan",
            entity_id=scan_id,
            payload={
                "subject_id": subject_id,
                "session_id": session_id,
                "scan_number": scan_number,
                "study_instance_uid": study_instance_uid
            }
        )
