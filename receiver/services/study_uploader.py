"""
Study Uploader Service
Uploads DICOM study archives to ITH API.
Supports chunked uploads for files larger than 2GB.
"""
import logging
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, TYPE_CHECKING
import requests

if TYPE_CHECKING:
    from receiver.services.ith_api_client import IthAPIClient

logger = logging.getLogger(__name__)

MAX_SINGLE_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
CHUNK_SIZE = 1.8 * 1024 * 1024 * 1024 


class StudyUploader:
    """
    Uploads DICOM study archives to ITH API.
    """

    def __init__(
        self,
        api_client: 'IthAPIClient',
        max_retries: int = 3,
        retry_delay: int = 5,
        cleanup_after_upload: bool = False
    ):
        """
        Initialize study uploader.

        Args:
            api_client: IthAPIClient instance
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            cleanup_after_upload: Whether to delete files after successful upload
        """
        self.api_client = api_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cleanup_after_upload = cleanup_after_upload

        logger.info(f"Study uploader initialized:")
        logger.info(f"Max retries: {max_retries}")
        logger.info(f"Retry delay: {retry_delay}s")
        logger.info(f"Cleanup after upload: {cleanup_after_upload}")

    def upload_study(
        self,
        zip_path: Path,
        study_info: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Upload a study archive to ITH API with duplicate upload prevention.

        Args:
            zip_path: Path to ZIP archive
            study_info: Study metadata (name, patient_id, etc.)

        Returns:
            Tuple of (success, response_data)
        """
        # Validate ZIP file exists
        if not zip_path.exists():
            logger.error(f"ZIP file does not exist: {zip_path}")
            return False, None

        # Validate ZIP file is not empty
        file_size = zip_path.stat().st_size
        if file_size == 0:
            logger.error(f"ZIP file is empty: {zip_path}")
            return False, None

        study_uid = study_info.get('metadata', {}).get('study_uid', 'unknown')

        from receiver.services.dispatch_lock_manager import get_dispatch_lock_manager
        lock_manager = get_dispatch_lock_manager()
        lock_acquired = lock_manager.acquire_lock('upload', 'study', study_uid)

        if not lock_acquired:
            logger.warning(f"🔒 Upload already in progress for study {study_uid}, skipping duplicate")
            return False, {'error': 'Upload already in progress'}

        try:
            if file_size > MAX_SINGLE_UPLOAD_SIZE:
                logger.warning(f"Large file detected: {file_size / 1024 / 1024 / 1024:.2f} GB")
                logger.info(f"Splitting study into smaller scans for upload...")
                return self._upload_large_study(zip_path, study_info, file_size)

            if file_size > 1024 * 1024 * 1024:
                logger.warning(f"Large file size: {file_size / 1024 / 1024:.2f} MB - upload may take time")

            attempt = 0
            last_error = None

            while attempt < self.max_retries:
                attempt += 1
                try:
                    logger.info(f" Uploading study (attempt {attempt}/{self.max_retries})")
                    logger.info(f"File: {zip_path.name}")
                    logger.info(f"Size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
                    logger.info(f"Study: {study_info.get('name', 'Unknown')}")

                    response_data = self._upload_to_api(zip_path, study_info)

                    if response_data:
                        logger.info(f" Study uploaded successfully:")
                        logger.info(f"Dataset ID: {response_data.get('id', 'N/A')}")
                        logger.info(f"Status: {response_data.get('status', 'N/A')}")
                        return True, response_data
                    else:
                        logger.warning(f"Upload attempt {attempt} failed - no response data")

                except Exception as e:
                    last_error = e
                    logger.warning(f"Upload attempt {attempt} failed: {e}")

                    if attempt < self.max_retries:
                        import time
                        logger.info(f"Retrying in {self.retry_delay} seconds...")
                        time.sleep(self.retry_delay)

            logger.error(f" Failed to upload study after {self.max_retries} attempts")
            if last_error:
                logger.error(f"Last error: {last_error}")

            return False, None

        finally:
            lock_manager.release_lock('upload', 'study', study_uid)

    def _upload_to_api(
        self,
        zip_path: Path,
        study_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Upload study ZIP to API endpoint.

        Args:
            zip_path: Path to ZIP file
            study_info: Study metadata

        Returns:
            Response data or None
        """
        try:
            # Validate API client configuration
            if not self.api_client or not hasattr(self.api_client, 'base_url'):
                logger.error("API client not properly configured")
                raise ValueError("API client missing or invalid")

            if not self.api_client.base_url:
                logger.error("API base URL is not set")
                raise ValueError("API base URL is empty")

            # Validate file exists and is readable
            if not zip_path.exists():
                logger.error(f"ZIP file does not exist: {zip_path}")
                raise FileNotFoundError(f"ZIP file not found: {zip_path}")

            if not zip_path.is_file():
                logger.error(f"Path is not a file: {zip_path}")
                raise ValueError(f"Not a file: {zip_path}")

            # Prepare file for upload
            with open(zip_path, 'rb') as f:
                files = {
                    'file': (zip_path.name, f, 'application/zip')
                }

                # Prepare metadata with validation
                data = {
                    'name': str(study_info.get('name', zip_path.stem))[:255],  # Limit length
                    'patient_id': str(study_info.get('patient_id', ''))[:255],
                    'study_description': str(study_info.get('description', ''))[:1000],
                    'metadata': study_info.get('metadata', {}),
                    'conflict_resolution': 'skip_existing'  # Skip if already exists
                }

                # Validate metadata is serializable
                try:
                    import json
                    json.dumps(data['metadata'])
                except (TypeError, ValueError) as e:
                    logger.warning(f"Metadata not JSON serializable, clearing: {e}")
                    data['metadata'] = {}

                # Upload using API client
                # Use correct endpoint: /api/v1/proxy/{workspace_id}/archives/upload
                if not self.api_client.workspace_id:
                    logger.error("Workspace ID not configured in API client")
                    raise ValueError("Workspace ID required for upload")

                url = f"{self.api_client.base_url}/api/v1/proxy/{self.api_client.workspace_id}/archives/upload"
                headers = self.api_client.headers.copy()

                # Validate headers (check for X-Proxy-Key)
                if not headers or 'X-Proxy-Key' not in headers:
                    logger.error("API headers missing or incomplete")
                    raise ValueError("API authorization not configured")

                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=300  # 5 minutes timeout for large files
                )

                if response.status_code in [200, 201]:
                    try:
                        return response.json()
                    except ValueError as e:
                        logger.error(f"Invalid JSON in API response: {e}")
                        logger.debug(f"Response text: {response.text[:500]}")
                        return None
                elif response.status_code == 401:
                    logger.error("API authentication failed - check credentials")
                    return None
                elif response.status_code == 413:
                    logger.error(f"File too large for API: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
                    return None
                elif response.status_code >= 500:
                    logger.error(f"API server error {response.status_code}: {response.text[:200]}")
                    return None
                else:
                    logger.error(f"API returned status {response.status_code}: {response.text[:200]}")
                    return None

        except requests.exceptions.Timeout:
            logger.error("Upload timeout - file may be too large or network slow")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during upload: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during upload: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error uploading to API: {e}", exc_info=True)
            raise

    def _upload_large_study(
        self,
        zip_path: Path,
        study_info: Dict[str, Any],
        total_size: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Upload a large study by splitting it into smaller scan-based chunks.
        Each chunk contains complete scans (series) to maintain data integrity.

        Args:
            zip_path: Path to large ZIP archive
            study_info: Study metadata
            total_size: Total file size in bytes

        Returns:
            Tuple of (success, response_data)
        """
        import tempfile
        import shutil

        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="upload_chunks_"))
            logger.info(f"Created temporary directory: {temp_dir}")

            extract_dir = temp_dir / "extracted"
            extract_dir.mkdir()

            logger.info(f"Extracting study to analyze structure...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            scans = self._group_files_by_series(extract_dir)
            logger.info(f"Found {len(scans)} scans (series) in study")

            if not scans:
                logger.error("No scans found in archive")
                return False, None

            chunks = self._create_scan_chunks(scans, extract_dir)
            logger.info(f"Split study into {len(chunks)} chunks for upload")

            uploaded_scan_ids = []
            for chunk_idx, chunk_scans in enumerate(chunks, 1):
                chunk_success, scan_ids = self._upload_chunk(
                    chunk_idx,
                    len(chunks),
                    chunk_scans,
                    extract_dir,
                    study_info,
                    temp_dir
                )

                if not chunk_success:
                    logger.error(f"Failed to upload chunk {chunk_idx}/{len(chunks)}")
                    return False, None

                uploaded_scan_ids.extend(scan_ids)

            logger.info(f"Successfully uploaded all {len(chunks)} chunks")
            logger.info(f"Total scans uploaded: {len(uploaded_scan_ids)}")

            return True, {
                'id': uploaded_scan_ids[0] if uploaded_scan_ids else None,
                'status': 'uploaded',
                'chunks': len(chunks),
                'total_scans': len(uploaded_scan_ids),
                'scan_ids': uploaded_scan_ids
            }

        except Exception as e:
            logger.error(f"Error uploading large study: {e}", exc_info=True)
            return False, None
        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Could not cleanup temp directory: {e}")

    def _group_files_by_series(self, extract_dir: Path) -> Dict[str, List[Path]]:
        """
        Group DICOM files by SeriesInstanceUID.

        Args:
            extract_dir: Directory containing extracted DICOM files

        Returns:
            Dict mapping SeriesInstanceUID to list of file paths
        """
        from pydicom import dcmread
        from pydicom.errors import InvalidDicomError

        scans = {}
        dcm_files = list(extract_dir.rglob('*.dcm'))

        logger.info(f"Analyzing {len(dcm_files)} DICOM files...")

        for dcm_file in dcm_files:
            try:
                ds = dcmread(str(dcm_file), stop_before_pixels=True)
                series_uid = getattr(ds, 'SeriesInstanceUID', 'UNKNOWN')

                if series_uid not in scans:
                    scans[series_uid] = []
                scans[series_uid].append(dcm_file)

            except (InvalidDicomError, Exception) as e:
                logger.warning(f"Could not read {dcm_file.name}: {e}")

        return scans

    def _create_scan_chunks(
        self,
        scans: Dict[str, List[Path]],
        extract_dir: Path
    ) -> List[List[str]]:
        """
        Create chunks of scans that fit within size limit.
        Keeps complete scans together - never splits a scan across chunks.

        Args:
            scans: Dict mapping SeriesInstanceUID to file paths
            extract_dir: Base directory

        Returns:
            List of chunks, where each chunk is a list of SeriesInstanceUIDs
        """
        scan_sizes = {}
        for series_uid, files in scans.items():
            total_size = sum(f.stat().st_size for f in files)
            scan_sizes[series_uid] = total_size

        sorted_scans = sorted(scan_sizes.items(), key=lambda x: x[1], reverse=True)

        chunks = []
        current_chunk = []
        current_size = 0

        for series_uid, size in sorted_scans:
            if size > CHUNK_SIZE:
                logger.warning(f"Scan {series_uid} ({size / 1024 / 1024:.2f} MB) exceeds chunk size, uploading alone")
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0
                chunks.append([series_uid])
                continue

            if current_size + size > CHUNK_SIZE and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0

            current_chunk.append(series_uid)
            current_size += size

        if current_chunk:
            chunks.append(current_chunk)

        for idx, chunk in enumerate(chunks, 1):
            chunk_size = sum(scan_sizes[uid] for uid in chunk)
            logger.info(f"Chunk {idx}: {len(chunk)} scans, {chunk_size / 1024 / 1024:.2f} MB")

        return chunks

    def _upload_chunk(
        self,
        chunk_idx: int,
        total_chunks: int,
        series_uids: List[str],
        extract_dir: Path,
        study_info: Dict[str, Any],
        temp_dir: Path
    ) -> Tuple[bool, List[str]]:
        """
        Upload a single chunk containing multiple scans.

        Args:
            chunk_idx: Current chunk index
            total_chunks: Total number of chunks
            series_uids: List of SeriesInstanceUIDs to include in this chunk
            extract_dir: Directory with extracted DICOM files
            study_info: Original study metadata
            temp_dir: Temporary directory for chunk ZIPs

        Returns:
            Tuple of (success, list of uploaded scan IDs)
        """
        try:
            chunk_zip_path = temp_dir / f"chunk_{chunk_idx}.zip"

            logger.info(f"Creating chunk {chunk_idx}/{total_chunks} with {len(series_uids)} scans...")

            file_count = 0
            with zipfile.ZipFile(chunk_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for dcm_file in extract_dir.rglob('*.dcm'):
                    try:
                        from pydicom import dcmread
                        ds = dcmread(str(dcm_file), stop_before_pixels=True)
                        series_uid = getattr(ds, 'SeriesInstanceUID', None)

                        if series_uid in series_uids:
                            arcname = dcm_file.relative_to(extract_dir)
                            zipf.write(dcm_file, arcname)
                            file_count += 1

                    except Exception as e:
                        logger.warning(f"Error adding {dcm_file.name} to chunk: {e}")

            chunk_size = chunk_zip_path.stat().st_size
            logger.info(f"Chunk {chunk_idx}: {file_count} files, {chunk_size / 1024 / 1024:.2f} MB")

            chunk_study_info = study_info.copy()
            chunk_study_info['name'] = f"{study_info.get('name', 'Study')} - Part {chunk_idx}/{total_chunks}"
            chunk_study_info['metadata'] = chunk_study_info.get('metadata', {}).copy()
            chunk_study_info['metadata']['chunk_index'] = chunk_idx
            chunk_study_info['metadata']['total_chunks'] = total_chunks
            chunk_study_info['metadata']['scan_count'] = len(series_uids)

            success, response_data = self.upload_study(chunk_zip_path, chunk_study_info)

            if success:
                scan_id = response_data.get('id') if response_data else None
                logger.info(f"Chunk {chunk_idx}/{total_chunks} uploaded successfully (ID: {scan_id})")
                return True, [scan_id] if scan_id else []
            else:
                logger.error(f"Chunk {chunk_idx}/{total_chunks} upload failed")
                return False, []

        except Exception as e:
            logger.error(f"Error uploading chunk {chunk_idx}: {e}", exc_info=True)
            return False, []


def get_study_uploader() -> Optional[StudyUploader]:
    """
    Get study uploader instance from DI container.

    Returns:
        StudyUploader instance or None
    """
    try:
        from receiver.containers import container
        from django.conf import settings

        api_client = container.ith_api_client()

        # Get settings
        max_retries = getattr(settings, 'UPLOAD_MAX_RETRIES', 3)
        retry_delay = getattr(settings, 'UPLOAD_RETRY_DELAY', 5)
        cleanup_after_upload = getattr(settings, 'CLEANUP_AFTER_UPLOAD', False)

        return StudyUploader(
            api_client=api_client,
            max_retries=max_retries,
            retry_delay=retry_delay,
            cleanup_after_upload=cleanup_after_upload
        )

    except Exception as e:
        logger.warning(f"Could not create study uploader: {e}")
        return None
