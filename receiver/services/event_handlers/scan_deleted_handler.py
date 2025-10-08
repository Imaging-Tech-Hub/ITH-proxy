"""
Scan Deleted Event Handler.
Handles scan.deleted events from ITH backend.
"""
import logging
from typing import Dict, Any
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ScanDeletedHandler:
    """
    Handles scan.deleted events.
    Cleans up local scan data if stored in database.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle scan.deleted event.

        Event structure:
        {
          "event_type": "scan.deleted",
          "workspace_id": "ws_abc123",
          "entity_type": "scan",
          "entity_id": "scan_jkl012",
          "payload": {
            "subject_id": "subj_ghi789",
            "session_id": "sess_def456",
            "scan_number": 3,
            "study_instance_uid": "1.2.3.4.5.6"
          }
        }

        Args:
            event_data: Event data from WebSocket

        Returns:
            bool: True if handled successfully
        """
        try:
            workspace_id = event_data.get('workspace_id')
            scan_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})
            subject_id = payload.get('subject_id')
            session_id = payload.get('session_id')
            scan_number = payload.get('scan_number')
            study_instance_uid = payload.get('study_instance_uid')

            logger.info("=" * 60)
            logger.info(f"🗑️  SCAN DELETED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Scan: {scan_id}")
            if scan_number:
                logger.info(f"Scan Number: {scan_number}")
            logger.info(f"Session: {session_id}")
            logger.info(f"Subject: {subject_id}")
            if study_instance_uid:
                logger.info(f"Study UID: {study_instance_uid}")
            logger.info("=" * 60)

            deleted = await self._delete_scan_from_database(study_instance_uid, scan_number)

            if deleted:
                logger.info(f" Scan deleted from local database")
            else:
                logger.info(f"ℹ️  Scan not found in local database (already cleaned up)")

            return True

        except Exception as e:
            logger.error(f" Error handling scan.deleted event: {e}", exc_info=True)
            return False

    async def _delete_scan_from_database(self, study_instance_uid: str, scan_number: int) -> bool:
        """
        Delete scan from local database if it exists.

        Args:
            study_instance_uid: Study Instance UID to find the session
            scan_number: Scan number to identify the scan

        Returns:
            bool: True if scan was found and deleted
        """
        if not study_instance_uid:
            logger.warning("No study_instance_uid provided, cannot delete from database")
            return False

        try:
            from receiver.models import Session, Scan

            def _delete():
                try:
                    session = Session.objects.filter(
                        study_instance_uid=study_instance_uid
                    ).first()

                    if not session:
                        logger.debug(f"Session {study_instance_uid} not found in database")
                        return False

                    scan_query = session.scans.all()

                    if scan_number is not None:
                        scan = scan_query.filter(series_number=scan_number).first()
                    else:
                        logger.warning("No scan_number provided, cannot identify specific scan")
                        return False

                    if scan:
                        instances_count = scan.instances_count
                        series_uid = scan.series_instance_uid

                        scan.delete()

                        logger.info(f"Deleted scan (Series: {series_uid}, {instances_count} instances)")
                        return True
                    else:
                        logger.debug(f"Scan #{scan_number} not found in session {study_instance_uid}")
                        return False

                except Exception as e:
                    logger.error(f"Error deleting scan from database: {e}", exc_info=True)
                    return False

            return await sync_to_async(_delete)()

        except Exception as e:
            logger.error(f"Error in database deletion: {e}", exc_info=True)
            return False
