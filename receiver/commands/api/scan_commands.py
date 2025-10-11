"""
Scan-related commands for ITH API.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from receiver.commands.base import Command, CommandResult
from receiver.services.api import IthAPIClient


class ListScansCommand(Command):
    """
    List all scans for a session with optional filters.

    Usage:
        cmd = ListScansCommand(client, "subj_abc", "sess_def", modality="MR")
        result = cmd.execute()
        if result:
            scans = result.data['scans']
    """

    def __init__(
        self,
        client: IthAPIClient,
        subject_id: str,
        session_id: str,
        **filters
    ):
        """
        Initialize command.

        Args:
            client: ITH API client
            subject_id: Subject ID (required)
            session_id: Session ID (required)
            **filters: Optional filters (modality, quality, etc.)
        """
        super().__init__()
        self.client = client
        self.subject_id = subject_id
        self.session_id = session_id
        self.filters = filters

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.subject_id:
            self.logger.error("subject_id is required")
            return False
        if not self.session_id:
            self.logger.error("session_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute list scans command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: subject_id and session_id are required"
            )

        try:
            self.logger.info(f"Listing scans for session {self.session_id} with filters: {self.filters}")
            data = self.client.list_scans(self.subject_id, self.session_id, **self.filters)

            scans_count = len(data.get('scans', []))
            self.logger.info(f"Found {scans_count} scans")

            return CommandResult(
                success=True,
                data=data,
                metadata={'count': scans_count}
            )
        except Exception as e:
            self.logger.error(f"Failed to list scans: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class GetScanCommand(Command):
    """
    Get specific scan by ID.

    Usage:
        cmd = GetScanCommand(client, "scan_ghi789")
        result = cmd.execute()
        if result:
            scan = result.data['scan']
    """

    def __init__(self, client: IthAPIClient, scan_id: str, include_deleted: bool = False):
        """
        Initialize command.

        Args:
            client: ITH API client
            scan_id: Scan identifier
            include_deleted: Include if soft-deleted
        """
        super().__init__()
        self.client = client
        self.scan_id = scan_id
        self.include_deleted = include_deleted

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.scan_id:
            self.logger.error("scan_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute get scan command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: scan_id is required"
            )

        try:
            self.logger.info(f"Getting scan: {self.scan_id}")
            data = self.client.get_scan(self.scan_id, self.include_deleted)

            return CommandResult(
                success=True,
                data=data
            )
        except Exception as e:
            self.logger.error(f"Failed to get scan {self.scan_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class DownloadScanCommand(Command):
    """
    Download scan archive containing DICOM files.

    Usage:
        cmd = DownloadScanCommand(
            client,
            "scan_ghi789",
            "subj_abc123",
            "sess_def456",
            Path("/downloads/scan.zip")
        )
        result = cmd.execute()
        if result:
            file_path = result.data['file_path']
    """

    def __init__(
        self,
        client: IthAPIClient,
        scan_id: str,
        subject_id: str,
        session_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6
    ):
        """
        Initialize command.

        Args:
            client: ITH API client
            scan_id: Scan identifier
            subject_id: Parent subject ID
            session_id: Parent session ID
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
        """
        super().__init__()
        self.client = client
        self.scan_id = scan_id
        self.subject_id = subject_id
        self.session_id = session_id
        self.output_path = Path(output_path)
        self.compression_format = compression_format
        self.compression_level = compression_level

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.scan_id:
            self.logger.error("scan_id is required")
            return False

        if not self.subject_id:
            self.logger.error("subject_id is required")
            return False

        if not self.session_id:
            self.logger.error("session_id is required")
            return False

        if self.compression_format not in ['zip', 'tar.gz']:
            self.logger.error(f"Invalid compression format: {self.compression_format}")
            return False

        if not (0 <= self.compression_level <= 9):
            self.logger.error(f"Compression level must be 0-9, got: {self.compression_level}")
            return False

        return True

    def execute(self) -> CommandResult:
        """Execute download scan command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            self.logger.info(f"Downloading scan {self.scan_id} to {self.output_path}")

            file_path = self.client.download_scan(
                self.scan_id,
                self.subject_id,
                self.session_id,
                self.output_path,
                self.compression_format,
                self.compression_level
            )

            file_size = file_path.stat().st_size
            self.logger.info(f"Download complete: {file_size} bytes")

            return CommandResult(
                success=True,
                data={
                    'file_path': str(file_path),
                    'file_size': file_size
                },
                metadata={
                    'scan_id': self.scan_id,
                    'subject_id': self.subject_id,
                    'session_id': self.session_id,
                    'compression_format': self.compression_format
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to download scan {self.scan_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )
