"""
Study Uploader Service
Uploads DICOM study archives to Laminate API.
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
import requests

if TYPE_CHECKING:
    from receiver.services.laminate_api_client import LaminateAPIClient

logger = logging.getLogger(__name__)


class StudyUploader:
    """
    Uploads DICOM study archives to Laminate API.
    """

    def __init__(
        self,
        api_client: 'LaminateAPIClient',
        max_retries: int = 3,
        retry_delay: int = 5,
        cleanup_after_upload: bool = False
    ):
        """
        Initialize study uploader.

        Args:
            api_client: LaminateAPIClient instance
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
        Upload a study archive to Laminate API.

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

        # Validate file size is reasonable (warn if > 1GB)
        if file_size > 1024 * 1024 * 1024:  # 1GB
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

                # Upload via API client
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


def get_study_uploader() -> Optional[StudyUploader]:
    """
    Get study uploader instance from DI container.

    Returns:
        StudyUploader instance or None
    """
    try:
        from receiver.containers import container
        from django.conf import settings

        api_client = container.laminate_api_client()

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
