"""
DICOM SCU (Service Class User) - Client for sending DICOM files to PACS.
"""
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from pynetdicom import AE, StoragePresentationContexts
from pynetdicom.sop_class import Verification
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

logger = logging.getLogger('receiver.dicom_scu')


class DICOMSendResult:
    """Result of DICOM send operation."""

    def __init__(self, success: bool, files_sent: int = 0, files_failed: int = 0, error: Optional[str] = None):
        self.success = success
        self.files_sent = files_sent
        self.files_failed = files_failed
        self.error = error
        self.total_files = files_sent + files_failed

    def __bool__(self):
        return self.success

    def __str__(self):
        if self.success:
            return f"Success: {self.files_sent}/{self.total_files} files sent"
        else:
            return f"Failed: {self.files_sent}/{self.total_files} files sent, {self.files_failed} failed. Error: {self.error}"


class DICOMServiceUser:
    """
    DICOM SCU for sending files to PACS nodes using C-STORE.
    """

    @staticmethod
    def validate_ae_title(ae_title: str) -> str:
        """
        Validate and normalize AE Title according to DICOM standard.

        DICOM Standard: AE Titles must be 1-16 characters, uppercase letters,
        digits, spaces, and underscores only.

        Args:
            ae_title: AE Title to validate

        Returns:
            str: Validated and normalized AE Title (truncated to 16 chars if needed)
        """
        if not ae_title:
            raise ValueError("AE Title cannot be empty")

        if len(ae_title) > 16:
            original = ae_title
            ae_title = ae_title[:16]
            logger.warning(f"AE Title '{original}' exceeds 16 characters, truncated to '{ae_title}'")

        return ae_title

    def __init__(
        self,
        ae_title: str = 'DICOM_PROXY',
        max_pdu_size: int = 16384,
        connection_timeout: int = 30,
        verification_only: bool = False
    ):
        """
        Initialize DICOM SCU.

        Args:
            ae_title: AE Title for this SCU (max 16 characters)
            max_pdu_size: Maximum PDU size in bytes
            connection_timeout: Connection timeout in seconds
            verification_only: If True, only add Verification context (for C-ECHO only)
        """
        ae_title = self.validate_ae_title(ae_title)

        self.ae_title = ae_title.encode() if isinstance(ae_title, str) else ae_title
        self.max_pdu_size = max_pdu_size
        self.connection_timeout = connection_timeout

        self.ae = AE(ae_title=self.ae_title)

        if verification_only:
            self.ae.add_requested_context(Verification)
        else:
            self.ae.requested_contexts = StoragePresentationContexts

    def verify_connection(
        self,
        host: str,
        port: int,
        called_ae_title: str
    ) -> bool:
        """
        Verify connection to PACS node using C-ECHO.

        Args:
            host: PACS hostname or IP
            port: PACS port
            called_ae_title: PACS AE Title (max 16 characters)

        Returns:
            bool: True if connection successful
        """
        try:
            called_ae_title = self.validate_ae_title(called_ae_title)

            logger.info(f"Verifying connection to {called_ae_title}@{host}:{port}")

            assoc = self.ae.associate(
                host,
                port,
                ae_title=called_ae_title.encode() if isinstance(called_ae_title, str) else called_ae_title,
                max_pdu=self.max_pdu_size
            )

            if assoc.is_established:
                status = assoc.send_c_echo()

                assoc.release()

                if status and status.Status == 0x0000:
                    logger.info(f" Connection verified to {called_ae_title}@{host}:{port}")
                    return True
                else:
                    logger.warning(f"C-ECHO failed with status: {status}")
                    return False
            else:
                logger.error(f"Failed to establish association with {called_ae_title}@{host}:{port}")
                return False

        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False

    def send_files(
        self,
        files: List[Path],
        host: str,
        port: int,
        called_ae_title: str,
        retry_count: int = 3,
        retry_delay: int = 5
    ) -> DICOMSendResult:
        """
        Send DICOM files to PACS node.

        Args:
            files: List of DICOM file paths
            host: PACS hostname or IP
            port: PACS port
            called_ae_title: PACS AE Title (max 16 characters)
            retry_count: Number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            DICOMSendResult: Result of send operation
        """
        if not files:
            logger.warning("No files to send")
            return DICOMSendResult(success=True, files_sent=0)

        called_ae_title = self.validate_ae_title(called_ae_title)

        logger.info(f"Sending {len(files)} files to {called_ae_title}@{host}:{port}")

        files_sent = 0
        files_failed = 0
        last_error = None

        for attempt in range(retry_count):
            try:
                assoc = self.ae.associate(
                    host,
                    port,
                    ae_title=called_ae_title.encode() if isinstance(called_ae_title, str) else called_ae_title,
                    max_pdu=self.max_pdu_size
                )

                if not assoc.is_established:
                    error_msg = f"Failed to establish association (attempt {attempt + 1}/{retry_count})"
                    logger.error(error_msg)
                    last_error = error_msg

                    if attempt < retry_count - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return DICOMSendResult(
                            success=False,
                            files_sent=files_sent,
                            files_failed=len(files),
                            error=error_msg
                        )

                for file_path in files:
                    try:
                        dataset = dcmread(str(file_path))

                        status = assoc.send_c_store(dataset)

                        if status and status.Status == 0x0000:
                            files_sent += 1
                            logger.debug(f" Sent: {file_path.name}")
                        else:
                            files_failed += 1
                            logger.error(f" Failed to send {file_path.name}: Status {status.Status if status else 'None'}")
                            last_error = f"C-STORE failed for {file_path.name}"

                    except InvalidDicomError as e:
                        files_failed += 1
                        logger.error(f" Invalid DICOM file {file_path}: {e}")
                        last_error = str(e)

                    except Exception as e:
                        files_failed += 1
                        logger.error(f" Error sending {file_path}: {e}")
                        last_error = str(e)

                assoc.release()

                logger.info(f" Sent {files_sent}/{len(files)} files successfully")
                return DICOMSendResult(
                    success=files_failed == 0,
                    files_sent=files_sent,
                    files_failed=files_failed,
                    error=last_error if files_failed > 0 else None
                )

            except Exception as e:
                error_msg = f"Error during send (attempt {attempt + 1}/{retry_count}): {e}"
                logger.error(error_msg)
                last_error = error_msg

                if attempt < retry_count - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    return DICOMSendResult(
                        success=False,
                        files_sent=files_sent,
                        files_failed=len(files) - files_sent,
                        error=error_msg
                    )

        return DICOMSendResult(
            success=False,
            files_sent=files_sent,
            files_failed=files_failed,
            error=last_error
        )

    def send_directory(
        self,
        directory: Path,
        host: str,
        port: int,
        called_ae_title: str,
        recursive: bool = True,
        retry_count: int = 3,
        retry_delay: int = 5
    ) -> DICOMSendResult:
        """
        Send all DICOM files in a directory to PACS node.

        Args:
            directory: Directory containing DICOM files
            host: PACS hostname or IP
            port: PACS port
            called_ae_title: PACS AE Title (max 16 characters)
            recursive: Recursively scan subdirectories
            retry_count: Number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            DICOMSendResult: Result of send operation
        """
        called_ae_title = self.validate_ae_title(called_ae_title)
        directory = Path(directory)

        if not directory.exists() or not directory.is_dir():
            error_msg = f"Directory does not exist: {directory}"
            logger.error(error_msg)
            return DICOMSendResult(success=False, error=error_msg)

        if recursive:
            dicom_files = list(directory.rglob('*.dcm'))
        else:
            dicom_files = list(directory.glob('*.dcm'))

        if not dicom_files:
            logger.warning(f"No DICOM files found in {directory}")
            return DICOMSendResult(success=True, files_sent=0)

        logger.info(f"Found {len(dicom_files)} DICOM files in {directory}")

        return self.send_files(
            dicom_files,
            host,
            port,
            called_ae_title,
            retry_count,
            retry_delay
        )
