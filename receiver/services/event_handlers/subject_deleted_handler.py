"""
Subject Deleted Event Handler.
Handles subject.deleted events from Laminate backend.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SubjectDeletedHandler:
    """
    Handles subject.deleted events.
    Cleans up local subject data if stored.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle subject.deleted event.

        Event structure:
        {
          "event_type": "subject.deleted",
          "workspace_id": "ws_abc123",
          "entity_type": "subject",
          "entity_id": "subj_ghi789",
          "payload": {
            "subject_identifier": "PATIENT-001"
          }
        }

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            subject_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})
            subject_identifier = payload.get('subject_identifier', 'Unknown')

            logger.info("=" * 60)
            logger.info(f"🗑️  SUBJECT DELETED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Subject: {subject_id}")
            logger.info(f"Identifier: {subject_identifier}")
            logger.info("=" * 60)


            logger.info("ℹ️  Subject deleted from backend - no local cleanup needed")
            logger.info(f"(Local files are already deleted after upload)")

            return True

        except Exception as e:
            logger.error(f" Error handling subject.deleted event: {e}", exc_info=True)
            return False
