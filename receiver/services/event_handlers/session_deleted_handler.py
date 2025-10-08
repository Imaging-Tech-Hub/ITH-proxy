"""
Session Deleted Event Handler.
Handles session.deleted events from ITH backend.
"""
import logging
from typing import Dict, Any
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class SessionDeletedHandler:
    """
    Handles session.deleted events.
    Cleans up local session data if stored in database.
    """

    async def handle(self, event_data: Dict[str, Any]) -> bool:
        """
        Handle session.deleted event.

        Event structure:
        {
          "event_type": "session.deleted",
          "workspace_id": "ws_abc123",
          "entity_type": "session",
          "entity_id": "sess_def456",
          "payload": {
            "subject_id": "subj_ghi789",
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
            session_id = event_data.get('entity_id')
            payload = event_data.get('payload', {})
            subject_id = payload.get('subject_id')
            study_instance_uid = payload.get('study_instance_uid')

            logger.info("=" * 60)
            logger.info(f"🗑️  SESSION DELETED EVENT RECEIVED")
            logger.info(f"Workspace: {workspace_id}")
            logger.info(f"Session: {session_id}")
            logger.info(f"Subject: {subject_id}")
            if study_instance_uid:
                logger.info(f"Study UID: {study_instance_uid}")
            logger.info("=" * 60)

            deleted = await self._delete_session_from_database(study_instance_uid)

            if deleted:
                logger.info(f" Session deleted from local database")
            else:
                logger.info(f"ℹ️  Session not found in local database (already cleaned up)")

            return True

        except Exception as e:
            logger.error(f" Error handling session.deleted event: {e}", exc_info=True)
            return False

    async def _delete_session_from_database(self, study_instance_uid: str) -> bool:
        """
        Delete session from local database if it exists.

        Args:
            study_instance_uid: Study Instance UID to find and delete

        Returns:
            bool: True if session was found and deleted
        """
        if not study_instance_uid:
            logger.warning("No study_instance_uid provided, cannot delete from database")
            return False

        try:
            from receiver.models import Session

            def _delete():
                try:
                    session = Session.objects.filter(
                        study_instance_uid=study_instance_uid
                    ).first()

                    if session:
                        scans_count = session.scans.count()
                        instances_count = sum(s.instances_count for s in session.scans.all())

                        session.delete()

                        logger.info(f"Deleted session with {scans_count} scans, {instances_count} instances")
                        return True
                    else:
                        logger.debug(f"Session {study_instance_uid} not found in database")
                        return False

                except Exception as e:
                    logger.error(f"Error deleting session from database: {e}", exc_info=True)
                    return False

            return await sync_to_async(_delete)()

        except Exception as e:
            logger.error(f"Error in database deletion: {e}", exc_info=True)
            return False
