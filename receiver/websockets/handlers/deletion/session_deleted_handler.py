"""SessionDeleted Handler."""
"""
Deletion Event Handlers.
Handle session and scan deletion events from backend.
"""
from typing import Dict, Any
from pathlib import Path
from ..base import BaseEventHandler
from receiver.models import Session, Scan


class SessionDeletedHandler(BaseEventHandler):
    """
    Handle session.deleted events.

    Action Required:
    1. Remove session from local PACS database
    2. Remove all scans belonging to this session
    3. Update subject's session count
    4. Use study_instance_uid to identify the correct DICOM study
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle session deletion event.

        Backend sends:
        {
          "event_type": "session.deleted",
          "entity_id": "7257cffb-e067-4a83-ac63-14889a527871",
          "payload": {
            "subject_id": "adb85943-6e7e-4e27-b4ec-566d03369e76",
            "session_label": "ses-001",
            "study_instance_uid": "1.3.12.2.1107.5.2.43.166194.30000022051108155375500000013"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        study_instance_uid = payload.get('study_instance_uid')
        session_label = payload.get('session_label')

        self.logger.info(f"Handling session deletion: {entity_id} (Study UID: {study_instance_uid})")

        try:
            session = await self._get_session_by_study_uid(study_instance_uid)

            if session:
                await self._delete_session(session)
                self.logger.info(f"Deleted session: {session_label} (Study UID: {study_instance_uid})")
            else:
                self.logger.warning(f"Session not found for Study UID: {study_instance_uid}")

        except Exception as e:
            self.logger.error(f"Error deleting session {entity_id}: {e}", exc_info=True)

    async def _get_session_by_study_uid(self, study_instance_uid: str):
        """Get session from database by Study Instance UID."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _get():
            try:
                return Session.objects.get(study_instance_uid=study_instance_uid)
            except Session.DoesNotExist:
                return None

        return await _get()

    async def _delete_session(self, session):
        """Delete session (uses custom delete() method that handles cleanup)."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _delete():
            session.delete()

        await _delete()
