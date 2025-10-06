"""
Study Monitor Module
Monitors study activity and detects when studies are complete.
"""
import logging
import threading
import time
from typing import Callable, List, Set, Dict, Optional
from django.conf import settings

logger = logging.getLogger('receiver.study_monitor')


class StudyMonitor:
    """
    Monitors study activity and detects when studies are complete
    based on a timeout since the last received file.
    """

    def __init__(self, timeout: Optional[int] = None) -> None:
        """
        Initialize the study monitor.

        Args:
            timeout: Timeout in seconds after receiving the last file in a study
        """
        self.timeout: int = timeout or getattr(settings, 'DICOM_STUDY_TIMEOUT', 60)
        self.study_last_activity: Dict[str, float] = {}
        self.study_monitor_lock: threading.Lock = threading.Lock()
        self.active_studies: Set[str] = set()
        self.study_complete_callbacks: List[Callable[[str], None]] = []

        self.monitor_thread: threading.Thread = threading.Thread(
            target=self._monitor_studies_timeout,
            daemon=True
        )
        self.monitor_thread.start()

        logger.info(f"Study monitor initialized with {self.timeout}s timeout")

    def register_study_complete_callback(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback to be called when a study is complete.

        Args:
            callback: Function to call with study_uid as parameter
        """
        self.study_complete_callbacks.append(callback)
        logger.info(f"Registered study complete callback: {callback.__name__}")

    def update_study_activity(self, study_uid: str) -> None:
        """
        Update the last activity timestamp for a study.

        Args:
            study_uid: Study Instance UID
        """
        now = time.time()
        with self.study_monitor_lock:
            self.study_last_activity[study_uid] = now
            self.active_studies.add(study_uid)
            logger.debug(f"Updated activity for study: {study_uid}")

    def _monitor_studies_timeout(self) -> None:
        """Monitor studies for timeout since last activity."""
        logger.info("Study timeout monitor started")

        while True:
            current_time = time.time()
            studies_to_finalize = []

            with self.study_monitor_lock:
                for study_uid, last_activity in list(self.study_last_activity.items()):
                    if current_time - last_activity > self.timeout:
                        studies_to_finalize.append(study_uid)
                        self.study_last_activity.pop(study_uid)

            for study_uid in studies_to_finalize:
                self._finalize_study(study_uid)

            time.sleep(1)

    def _finalize_study(self, study_uid: str) -> None:
        """
        Finalize a study after timeout.

        Args:
            study_uid: Study Instance UID
        """
        logger.info(f"🏁 Finalizing study {study_uid} after {self.timeout}s timeout")

        should_finalize = False
        with self.study_monitor_lock:
            if study_uid in self.active_studies:
                self.active_studies.remove(study_uid)
                should_finalize = True

        if should_finalize:
            logger.info(f" Study {study_uid} completed")

            for callback in self.study_complete_callbacks:
                try:
                    callback(study_uid)
                except Exception as e:
                    logger.error(f" Error in study complete callback: {e}", exc_info=True)

    def get_active_studies(self) -> Set[str]:
        """Get set of currently active study UIDs."""
        with self.study_monitor_lock:
            return self.active_studies.copy()

    def get_study_count(self) -> int:
        """Get count of active studies."""
        with self.study_monitor_lock:
            return len(self.active_studies)
