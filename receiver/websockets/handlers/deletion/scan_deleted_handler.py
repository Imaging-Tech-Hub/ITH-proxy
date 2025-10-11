"""ScanDeleted Handler."""
"""
Deletion Event Handlers.
Handle session and scan deletion events from backend.
"""
from typing import Dict, Any
from pathlib import Path
from ..base import BaseEventHandler
from receiver.models import Session, Scan


class ScanDeletedHandler(BaseEventHandler):
    """
    Handle scan.deleted events.

    Action Required:
    1. Remove scan from local PACS database
    2. Update session's scan count
    3. Use study_instance_uid to identify the correct DICOM study
    """

    async def handle(self, event: Dict[str, Any]) -> None:
        """
        Handle scan deletion event.

        Payload:
        {
          "entity_id": "scan_jkl012",
          "payload": {
            "subject_id": "subj_ghi789",
            "session_id": "sess_def456",
            "scan_number": 3,
            "study_instance_uid": "1.2.840.113619.2.55.3.123456789.1234"
          }
        }
        """
        entity_id = event.get('entity_id')
        payload = event.get('payload', {})
        study_instance_uid = payload.get('study_instance_uid')
        scan_number = payload.get('scan_number')

        self.logger.info(f"Handling scan deletion: {entity_id} (Scan #{scan_number}, Study UID: {study_instance_uid})")

        try:
            scan = await self._get_scan_by_study_and_number(study_instance_uid, scan_number)

            if scan:
                await self._delete_scan(scan)
                self.logger.info(f"Deleted scan #{scan_number} from Study UID: {study_instance_uid}")
            else:
                self.logger.warning(f"Scan not found for Study UID: {study_instance_uid}, Scan #: {scan_number}")

        except Exception as e:
            self.logger.error(f"Error deleting scan {entity_id}: {e}", exc_info=True)

    async def _get_scan_by_study_and_number(self, study_instance_uid: str, scan_number: int):
        """Get scan from database by Study Instance UID and scan number."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _get():
            try:
                session = Session.objects.get(study_instance_uid=study_instance_uid)
                return Scan.objects.get(session=session, series_number=scan_number)
            except (Session.DoesNotExist, Scan.DoesNotExist):
                return None

        return await _get()

    async def _delete_scan(self, scan):
        """Delete scan."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def _delete():
            if scan.storage_path:
                import shutil
                storage_path = Path(scan.storage_path)
                if storage_path.exists():
                    shutil.rmtree(storage_path, ignore_errors=True)

            scan.delete()

        await _delete()
