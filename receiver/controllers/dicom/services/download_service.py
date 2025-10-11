"""
Download service for retrieving DICOM datasets from the ITH API.

Handles downloading at different query levels (STUDY, SERIES, IMAGE).
"""
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from pydicom import dcmread

if TYPE_CHECKING:
    from receiver.controllers.phi import PHIResolver

logger = logging.getLogger('receiver.services.download')


class DICOMDownloadService:
    """
    Service for downloading DICOM datasets from ITH API.

    Handles:
    - Study-level downloads
    - Series-level downloads
    - Image-level downloads
    - Lock management to prevent duplicate downloads
    """

    def __init__(
        self,
        api_client: Any,
        resolver: 'PHIResolver',
        lock_manager: Optional[Any] = None
    ):
        """
        Initialize download service.

        Args:
            api_client: ITH API client for making requests
            resolver: PHIResolver for de-anonymization
            lock_manager: Optional lock manager to prevent concurrent downloads
        """
        self.api_client = api_client
        self.resolver = resolver
        self.lock_manager = lock_manager

    def download_study(
        self,
        study_uid: str,
        transfer_syntax: str,
        prepare_dataset_func: Any
    ) -> list:
        """
        Download all datasets for a study.

        Args:
            study_uid: Study Instance UID
            transfer_syntax: Transfer syntax to use
            prepare_dataset_func: Function to prepare each dataset

        Returns:
            List of DICOM datasets
        """
        datasets = []

        try:
            logger.info(f"Searching for study {study_uid} in API sessions...")
            sessions_response = self.api_client.list_sessions()
            sessions = sessions_response.get('sessions', [])
            logger.info(f"Found {len(sessions)} sessions in API")

            matched = False
            for session in sessions:
                session_study_uid = session.get('study_instance_uid')
                if session_study_uid == study_uid:
                    matched = True
                    session_id = session.get('session_id')
                    subject_id = session.get('subject_id')
                    logger.info(f"Matched session {session_id} with study UID {study_uid}")

                    if session_id and subject_id:
                        datasets = self._download_session(
                            session_id,
                            subject_id,
                            study_uid,
                            transfer_syntax,
                            prepare_dataset_func,
                            lock_key='c-get'
                        )
                    break

            if not matched:
                logger.warning(f"No session found in API with StudyInstanceUID: {study_uid}")
                logger.warning(f"Available study UIDs: {[s.get('study_instance_uid') for s in sessions[:5]]}")

        except Exception as e:
            logger.error(f"Error downloading study: {e}", exc_info=True)

        return datasets

    def download_series(
        self,
        study_uid: str,
        series_uid: str,
        transfer_syntax: str,
        prepare_dataset_func: Any
    ) -> list:
        """
        Download all datasets for a series.

        Args:
            study_uid: Study Instance UID
            series_uid: Series Instance UID
            transfer_syntax: Transfer syntax to use
            prepare_dataset_func: Function to prepare each dataset

        Returns:
            List of DICOM datasets
        """
        datasets = []

        try:
            sessions_response = self.api_client.list_sessions()
            sessions = sessions_response.get('sessions', [])

            for session in sessions:
                if session.get('study_instance_uid') == study_uid:
                    session_id = session.get('session_id')
                    subject_id = session.get('subject_id')

                    if not session_id or not subject_id:
                        continue

                    logger.debug(f"Finding scan with SeriesInstanceUID {series_uid}")
                    scans_response = self.api_client.list_scans(subject_id, session_id)
                    scans = scans_response.get('scans', [])

                    matching_scan = None
                    for scan in scans:
                        if scan.get('series_instance_uid') == series_uid:
                            matching_scan = scan
                            break

                    if not matching_scan:
                        logger.warning(f"No scan found with SeriesInstanceUID {series_uid}")
                        break

                    scan_id = matching_scan.get('id')
                    logger.info(f"Found matching scan: {scan_id}")

                    datasets = self._download_scan(
                        scan_id,
                        session_id,
                        subject_id,
                        series_uid,
                        transfer_syntax,
                        prepare_dataset_func
                    )
                    break

        except Exception as e:
            logger.error(f"Error downloading series: {e}", exc_info=True)

        return datasets

    def download_image(
        self,
        study_uid: str,
        series_uid: str,
        sop_uid: str,
        transfer_syntax: str,
        prepare_dataset_func: Any
    ) -> list:
        """
        Download a specific image.

        Args:
            study_uid: Study Instance UID
            series_uid: Series Instance UID
            sop_uid: SOP Instance UID
            transfer_syntax: Transfer syntax to use
            prepare_dataset_func: Function to prepare each dataset

        Returns:
            List containing single DICOM dataset
        """
        datasets = []

        try:
            sessions_response = self.api_client.list_sessions()
            sessions = sessions_response.get('sessions', [])

            for session in sessions:
                if session.get('study_instance_uid') == study_uid:
                    session_id = session.get('session_id')
                    subject_id = session.get('subject_id')

                    if session_id and subject_id:
                        lock_acquired = self._acquire_lock('api_download', 'c-get-image', sop_uid)

                        try:
                            with tempfile.TemporaryDirectory() as temp_dir:
                                temp_path = Path(temp_dir) / f"{session_id}.zip"

                                logger.info(f"Downloading session {session_id} for image {sop_uid}...")
                                self.api_client.download_session(
                                    session_id=session_id,
                                    subject_id=subject_id,
                                    output_path=temp_path
                                )

                                extract_dir = Path(temp_dir) / "extracted"
                                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                                    zip_ref.extractall(extract_dir)

                                for dcm_file in extract_dir.rglob('*.dcm'):
                                    try:
                                        ds = dcmread(str(dcm_file))
                                        if (getattr(ds, 'SeriesInstanceUID', None) == series_uid and
                                            getattr(ds, 'SOPInstanceUID', None) == sop_uid):
                                            ds = self.resolver.resolve_dataset(ds)
                                            prepare_dataset_func(ds, transfer_syntax)
                                            datasets.append(ds)
                                            break
                                    except Exception as e:
                                        logger.warning(f"Error reading {dcm_file}: {e}")

                        finally:
                            if lock_acquired:
                                self._release_lock('api_download', 'c-get-image', sop_uid)

                    break

        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)

        return datasets

    def _download_session(
        self,
        session_id: str,
        subject_id: str,
        study_uid: str,
        transfer_syntax: str,
        prepare_dataset_func: Any,
        lock_key: str
    ) -> list:
        """
        Download and extract all DICOM files from a session.

        Args:
            session_id: Session ID
            subject_id: Subject ID
            study_uid: Study UID for lock identification
            transfer_syntax: Transfer syntax to use
            prepare_dataset_func: Function to prepare each dataset
            lock_key: Lock key for preventing concurrent downloads

        Returns:
            List of DICOM datasets
        """
        datasets = []
        lock_acquired = self._acquire_lock('api_download', lock_key, study_uid)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"{session_id}.zip"

                logger.info(f"Downloading session {session_id} from API...")
                self.api_client.download_session(
                    session_id=session_id,
                    subject_id=subject_id,
                    output_path=temp_path
                )

                extract_dir = Path(temp_dir) / "extracted"
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                for dcm_file in extract_dir.rglob('*.dcm'):
                    try:
                        ds = dcmread(str(dcm_file))
                        ds = self.resolver.resolve_dataset(ds)
                        prepare_dataset_func(ds, transfer_syntax)
                        datasets.append(ds)
                    except Exception as e:
                        logger.warning(f"Error reading {dcm_file}: {e}")

        finally:
            if lock_acquired:
                self._release_lock('api_download', lock_key, study_uid)

        return datasets

    def _download_scan(
        self,
        scan_id: str,
        session_id: str,
        subject_id: str,
        series_uid: str,
        transfer_syntax: str,
        prepare_dataset_func: Any
    ) -> list:
        """
        Download and extract all DICOM files from a scan.

        Args:
            scan_id: Scan ID
            session_id: Session ID
            subject_id: Subject ID
            series_uid: Series UID for lock identification
            transfer_syntax: Transfer syntax to use
            prepare_dataset_func: Function to prepare each dataset

        Returns:
            List of DICOM datasets
        """
        datasets = []
        lock_acquired = self._acquire_lock('api_download', 'c-get-series', series_uid)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"{scan_id}.zip"

                logger.info(f"Downloading scan {scan_id} for series {series_uid}...")
                self.api_client.download_scan(
                    scan_id=scan_id,
                    subject_id=subject_id,
                    session_id=session_id,
                    output_path=temp_path
                )

                extract_dir = Path(temp_dir) / "extracted"
                logger.debug(f"Extracting ZIP file...")
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                dcm_files = list(extract_dir.rglob('*.dcm'))
                logger.info(f"Found {len(dcm_files)} DICOM files in scan")

                if not dcm_files:
                    all_files = list(extract_dir.rglob('*'))
                    logger.warning(f"No .dcm files found in archive. Files present: {[f.name for f in all_files[:10]]}")

                for dcm_file in dcm_files:
                    try:
                        ds = dcmread(str(dcm_file))
                        ds = self.resolver.resolve_dataset(ds)
                        prepare_dataset_func(ds, transfer_syntax)
                        datasets.append(ds)
                        logger.debug(f"Loaded instance: {dcm_file.name}")
                    except Exception as e:
                        logger.error(f"Error reading {dcm_file}: {e}", exc_info=True)

                logger.info(f"Successfully loaded {len(datasets)} DICOM instances from scan")

        finally:
            if lock_acquired:
                self._release_lock('api_download', 'c-get-series', series_uid)

        return datasets

    def _acquire_lock(self, node: str, operation: str, uid: str) -> bool:
        """
        Acquire a download lock to prevent concurrent downloads.

        Args:
            node: Node identifier
            operation: Operation type
            uid: UID to lock on

        Returns:
            True if lock was acquired, False if already locked
        """
        if not self.lock_manager:
            return False

        lock_acquired = self.lock_manager.acquire_lock(node, operation, uid)

        if not lock_acquired:
            logger.warning(f"Download already in progress for {uid}, waiting...")
            import time
            time.sleep(0.5)

        return lock_acquired

    def _release_lock(self, node: str, operation: str, uid: str) -> None:
        """
        Release a download lock.

        Args:
            node: Node identifier
            operation: Operation type
            uid: UID to unlock
        """
        if self.lock_manager:
            self.lock_manager.release_lock(node, operation, uid)
