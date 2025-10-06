"""
C-GET Handler for DICOM operations.
Handles C-GET requests to retrieve DICOM studies via same connection (no NAT issues).
"""
import logging
import tempfile
import zipfile
from pathlib import Path
from io import BytesIO
from typing import Any, Optional, TYPE_CHECKING

from pydicom import dcmread
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
import pydicom

if TYPE_CHECKING:
    from receiver.controllers.storage_manager import StorageManager
    from receiver.controllers.phi_resolver import PHIResolver
    from receiver.services.api_query_service import APIQueryService

logger = logging.getLogger('receiver.handlers.get')


class GetHandler:
    """
    Handler for DICOM C-GET operations.
    Retrieves DICOM files and sends them back on the same connection.

    Advantages over C-MOVE:
    - No NAT/firewall issues (uses same connection)
    - No port forwarding required
    - Simpler network setup
    """

    def __init__(
        self,
        storage_manager: 'StorageManager',
        resolver: 'PHIResolver',
        api_query_service: Optional['APIQueryService'] = None
    ):
        """
        Initialize C-GET handler.

        Args:
            storage_manager: StorageManager instance
            resolver: PHIResolver for de-anonymization
            api_query_service: APIQueryService for downloading from API
        """
        self.storage_manager = storage_manager
        self.resolver = resolver
        self.api_query_service = api_query_service

    def handle_get(self, event: Any):
        """
        Handle C-GET request.

        For C-GET, pynetdicom expects us to:
        1. Yield the number of sub-operations
        2. Yield datasets with status codes
        3. Return on the same connection (no new association)

        Args:
            event: pynetdicom C-GET event

        Yields:
            Dataset count, datasets with status codes
        """
        try:
            from receiver.services.access_control_service import extract_calling_ae_title, get_access_control_service
            calling_ae = extract_calling_ae_title(event)

            access_control = get_access_control_service()

            if access_control:
                allowed, reason = access_control.can_accept_retrieve(calling_ae, "C-GET")
                if not allowed:
                    logger.warning(f"C-GET REJECTED from {calling_ae}: {reason}")
                    yield 0xC001
                    return
                logger.debug(f"C-GET access granted to {calling_ae}: {reason}")

            request = event.request

            logger.info("=" * 60)
            logger.info("C-GET REQUEST RECEIVED")
            logger.info(f"From: {calling_ae}")

            identifier = request.Identifier

            if isinstance(identifier, BytesIO):
                logger.debug("Identifier is BytesIO, decoding to Dataset...")
                identifier.seek(0)
                identifier = dcmread(identifier, force=True)

            query_level = getattr(identifier, 'QueryRetrieveLevel', 'STUDY')
            logger.info(f"Query Level: {query_level}")

            self._log_query_parameters(identifier)

            study_uid = self._extract_study_uid(identifier)
            if not study_uid and query_level == 'STUDY':
                logger.error("No StudyInstanceUID provided for STUDY level C-GET")
                yield 0xA900  
                return

            self._configure_association_contexts(event)

            preferred_syntax = self._get_preferred_transfer_syntax(event)
            logger.info(f"Transfer Syntax: {preferred_syntax}")

            datasets = self._find_datasets(identifier, query_level, study_uid, preferred_syntax)

            if not datasets:
                logger.warning("No matching files found for C-GET request")
                yield 0xA701 
                return

            total_datasets = len(datasets)
            logger.info(f"Found {total_datasets} datasets to retrieve")

            yield total_datasets

            sent_count = 0
            for dataset in datasets:
                try:
                    sent_count += 1
                    logger.info(f"Sending dataset {sent_count}/{total_datasets}")
                    logger.debug(f"Patient: {getattr(dataset, 'PatientName', 'Unknown')}")
                    logger.debug(f"Study: {getattr(dataset, 'StudyInstanceUID', 'Unknown')}")

                    yield 0xFF00, dataset

                except Exception as e:
                    logger.error(f"Error processing dataset: {e}", exc_info=True)
                    yield 0xB000

            logger.info(f"C-GET completed: {sent_count}/{total_datasets} datasets sent")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error in C-GET handler: {e}", exc_info=True)
            yield 0xA701 

    def _log_query_parameters(self, identifier: Any) -> None:
        """Log query parameters from identifier."""
        logger.debug("Query Parameters:")
        logger.debug(f"Identifier type: {type(identifier)}")

        for elem in identifier:
            if elem.value is not None:
                if isinstance(elem.value, (str, int, float)):
                    value_str = str(elem.value)
                    display_value = value_str[:100] + "..." if len(value_str) > 100 else value_str
                else:
                    display_value = f"<{type(elem.value).__name__}>"
                logger.debug(f"{elem.keyword}: {display_value}")

    def _extract_study_uid(self, identifier: Any) -> Optional[str]:
        """Extract StudyInstanceUID from identifier."""
        for elem in identifier:
            if elem.keyword == 'StudyInstanceUID':
                if elem.value:
                    study_uid = str(elem.value).strip()
                    logger.info(f"Extracted StudyInstanceUID: {study_uid}")
                    return study_uid
                else:
                    logger.warning("StudyInstanceUID element exists but value is empty")

        logger.error("No StudyInstanceUID element found in identifier")
        return None

    def _configure_association_contexts(self, event: Any) -> None:
        """
        Configure association contexts for sending data back.
        Sets all accepted contexts as SCU for C-GET response.
        """
        try:
            for cx in event.assoc.accepted_contexts:
                cx._as_scu = True
        except Exception as e:
            logger.warning(f"Error configuring association contexts: {e}")

    def _get_preferred_transfer_syntax(self, event: Any) -> str:
        """
        Determine preferred transfer syntax from association.

        Returns:
            Transfer syntax UID
        """
        for cx in event.assoc.accepted_contexts:
            if cx.abstract_syntax.startswith('1.2.840.10008.5.1.4'): 
                if cx.transfer_syntax:
                    return cx.transfer_syntax[0]

        return ImplicitVRLittleEndian

    def _find_datasets(
        self,
        identifier: Any,
        query_level: str,
        study_uid: Optional[str],
        transfer_syntax: str
    ) -> list:
        """
        Find datasets matching the query.
        Always downloads from API to get the latest/processed version.

        Args:
            identifier: Query identifier
            query_level: Query level (STUDY, SERIES, IMAGE)
            study_uid: Study Instance UID
            transfer_syntax: Preferred transfer syntax

        Returns:
            List of DICOM datasets
        """
        datasets = []

        if self.api_query_service:
            logger.info("Downloading from Laminate API...")
            api_datasets = self._download_from_api(
                query_level, study_uid, identifier, transfer_syntax
            )

            if api_datasets:
                logger.info(f"Downloaded {len(api_datasets)} datasets from API")
                return api_datasets
            else:
                logger.warning("No data found in API")
        else:
            logger.error("No API access configured - cannot perform C-GET")

        return datasets

    def _download_from_api(
        self,
        query_level: str,
        study_uid: Optional[str],
        identifier: Any,
        transfer_syntax: str
    ) -> list:
        """
        Download datasets from Laminate API.

        Args:
            query_level: Query level
            study_uid: Study Instance UID
            identifier: Query identifier
            transfer_syntax: Transfer syntax to use

        Returns:
            List of DICOM datasets
        """
        datasets = []

        try:
            if query_level == 'STUDY' and study_uid:
                from receiver.containers import container
                api_client = container.laminate_api_client()

                sessions_response = api_client.list_sessions()
                sessions = sessions_response.get('sessions', [])

                for session in sessions:
                    if session.get('study_instance_uid') == study_uid:
                        session_id = session.get('session_id')
                        subject_id = session.get('subject_id')

                        if session_id and subject_id:
                            with tempfile.TemporaryDirectory() as temp_dir:
                                temp_path = Path(temp_dir) / f"{session_id}.zip"

                                logger.info(f"Downloading session {session_id} from API...")
                                api_client.download_session(
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

                                        self._prepare_dataset(ds, transfer_syntax)

                                        datasets.append(ds)
                                    except Exception as e:
                                        logger.warning(f"Error reading {dcm_file}: {e}")

                        break

            elif query_level == 'SERIES':
                series_uid = self._extract_series_uid(identifier)
                if study_uid and series_uid:
                    datasets = self._download_series_from_api(
                        study_uid, series_uid, transfer_syntax
                    )

            elif query_level == 'IMAGE':
                series_uid = self._extract_series_uid(identifier)
                sop_uid = self._extract_sop_uid(identifier)
                if study_uid and series_uid and sop_uid:
                    datasets = self._download_image_from_api(
                        study_uid, series_uid, sop_uid, transfer_syntax
                    )

        except Exception as e:
            logger.error(f"Error downloading from API: {e}", exc_info=True)

        return datasets

    def _download_series_from_api(
        self,
        study_uid: str,
        series_uid: str,
        transfer_syntax: str
    ) -> list:
        """Download specific series (scan) from API."""
        datasets = []

        try:
            from receiver.containers import container
            api_client = container.laminate_api_client()

            sessions_response = api_client.list_sessions()
            sessions = sessions_response.get('sessions', [])

            for session in sessions:
                if session.get('study_instance_uid') == study_uid:
                    session_id = session.get('session_id')
                    subject_id = session.get('subject_id')

                    if not session_id or not subject_id:
                        continue

                    logger.debug(f"Finding scan with SeriesInstanceUID {series_uid}")
                    scans_response = api_client.list_scans(subject_id, session_id)
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

                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir) / f"{scan_id}.zip"

                        logger.info(f"Downloading scan {scan_id} for series {series_uid}...")
                        api_client.download_scan(
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
                                self._prepare_dataset(ds, transfer_syntax)
                                datasets.append(ds)
                                logger.debug(f"Loaded instance: {dcm_file.name}")
                            except Exception as e:
                                logger.error(f"Error reading {dcm_file}: {e}", exc_info=True)

                        logger.info(f"Successfully loaded {len(datasets)} DICOM instances from scan")

                    break

        except Exception as e:
            logger.error(f"Error downloading series: {e}", exc_info=True)

        return datasets

    def _download_image_from_api(
        self,
        study_uid: str,
        series_uid: str,
        sop_uid: str,
        transfer_syntax: str
    ) -> list:
        """Download specific image from API."""
        datasets = []

        try:
            from receiver.containers import container
            api_client = container.laminate_api_client()

            sessions_response = api_client.list_sessions()
            sessions = sessions_response.get('sessions', [])

            for session in sessions:
                if session.get('study_instance_uid') == study_uid:
                    session_id = session.get('session_id')
                    subject_id = session.get('subject_id')

                    if session_id and subject_id:
                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_path = Path(temp_dir) / f"{session_id}.zip"

                            logger.info(f"Downloading session {session_id} for image {sop_uid}...")
                            api_client.download_session(
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
                                        self._prepare_dataset(ds, transfer_syntax)
                                        datasets.append(ds)
                                        break 
                                except Exception as e:
                                    logger.warning(f"Error reading {dcm_file}: {e}")

                    break

        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)

        return datasets

    def _extract_series_uid(self, identifier: Any) -> Optional[str]:
        """Extract SeriesInstanceUID from identifier."""
        for elem in identifier:
            if elem.keyword == 'SeriesInstanceUID' and elem.value:
                return str(elem.value).strip()
        return None

    def _extract_sop_uid(self, identifier: Any) -> Optional[str]:
        """Extract SOPInstanceUID from identifier."""
        for elem in identifier:
            if elem.keyword == 'SOPInstanceUID' and elem.value:
                return str(elem.value).strip()
        return None

    def _prepare_dataset(self, dataset: Any, transfer_syntax: str) -> None:
        """
        Prepare dataset with correct transfer syntax and file meta.

        Args:
            dataset: DICOM dataset to prepare
            transfer_syntax: Transfer syntax UID
        """
        try:
            if not hasattr(dataset, 'file_meta') or dataset.file_meta is None:
                dataset.file_meta = pydicom.dataset.FileMetaDataset()

            dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
            dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
            dataset.file_meta.TransferSyntaxUID = transfer_syntax
            dataset.file_meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
            dataset.file_meta.ImplementationVersionName = "PYDICOM"
            dataset.file_meta.FileMetaInformationVersion = b'\x00\x01'

        except Exception as e:
            logger.warning(f"Error preparing dataset: {e}")
