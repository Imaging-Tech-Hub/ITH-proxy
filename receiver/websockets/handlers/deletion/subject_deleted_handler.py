"""SubjectDeleted Handler."""
"""
Deletion Event Handler for subject deletion.
Handle subject.deleted events from backend.
"""
from typing import Dict, Any
from pathlib import Path
from ..base import BaseEventHandler
from receiver.models import PatientMapping, Session


class SubjectDeletedHandler(BaseEventHandler):
    """
    Handle subject.deleted events.

    Action Required:
    1. Remove all sessions belonging to this subject
    2. Remove all scans belonging to those sessions (cascade)
    3. Remove patient mapping from database
    4. Clean up storage directories

    Note: Subject corresponds to PatientMapping in the proxy database.
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle subject deletion event.

        Backend sends:
        {
          "event_type": "subject.deleted",
          "entity_id": "adb85943-6e7e-4e27-b4ec-566d03369e76",
          "payload": {
            "subject_identifier": "2135"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        subject_identifier = payload.get('subject_identifier')

        self.logger.info(f"Handling subject deletion: {entity_id} (Subject identifier: {subject_identifier})")

        if not subject_identifier:
            self.logger.warning(f"No subject_identifier found in subject.deleted event: {entity_id}")
            return

        try:
            # Get patient mapping by original patient ID
            patient_mapping = await self._get_patient_mapping_by_original_id(subject_identifier)

            if not patient_mapping:
                self.logger.warning(
                    f"Patient mapping not found for subject identifier '{subject_identifier}'. "
                    f"This is normal if the subject was never received by this proxy."
                )
                return

            # Get anonymous patient ID for session deletion
            anonymous_patient_id = patient_mapping.anonymous_patient_id

            # Delete all sessions for this patient (will cascade to scans and clean up storage)
            deleted_sessions = await self._delete_patient_sessions(anonymous_patient_id)

            # Delete patient mapping
            await self._delete_patient_mapping(patient_mapping)

            self.logger.info(
                f"Deleted subject {subject_identifier} (Anonymous: {anonymous_patient_id}): "
                f"{deleted_sessions} sessions removed, patient mapping removed"
            )

        except Exception as e:
            self.logger.error(f"Error deleting subject {entity_id}: {e}", exc_info=True)

    async def _get_patient_mapping_by_original_id(self, original_patient_id: str):
        """Get patient mapping from database by original patient ID."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _get():
            try:
                return PatientMapping.objects.get(original_patient_id=original_patient_id)
            except PatientMapping.DoesNotExist:
                return None

        return await _get()

    async def _delete_patient_sessions(self, anonymous_patient_id: str) -> int:
        """
        Delete all sessions for this patient.

        Returns:
            Number of sessions deleted
        """
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _delete():
            sessions = Session.objects.filter(patient_id=anonymous_patient_id)
            count = sessions.count()

            # Delete each session (triggers custom delete() method with cleanup)
            for session in sessions:
                session.delete()

            return count

        return await _delete()

    async def _delete_patient_mapping(self, patient_mapping):
        """Delete patient mapping."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _delete():
            patient_mapping.delete()

        await _delete()
