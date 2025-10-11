"""
Subject-related commands for ITH API.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from receiver.commands.base import Command, CommandResult
from receiver.services.api import IthAPIClient


class ListSubjectsCommand(Command):
    """
    List all subjects in workspace with optional filters.

    Usage:
        cmd = ListSubjectsCommand(client, species="human", sort_by="identifier")
        result = cmd.execute()
        if result:
            subjects = result.data['subjects']
    """

    def __init__(self, client: IthAPIClient, **filters):
        """
        Initialize command.

        Args:
            client: ITH API client
            **filters: Optional filters (species, search_query, etc.)
        """
        super().__init__()
        self.client = client
        self.filters = filters

    def execute(self) -> CommandResult:
        """Execute list subjects command."""
        try:
            self.logger.info(f"Listing subjects with filters: {self.filters}")
            data = self.client.list_subjects(**self.filters)

            subjects_count = len(data.get('subjects', []))
            self.logger.info(f"Found {subjects_count} subjects")

            return CommandResult(
                success=True,
                data=data,
                metadata={'count': subjects_count}
            )
        except Exception as e:
            self.logger.error(f"Failed to list subjects: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class GetSubjectCommand(Command):
    """
    Get specific subject by ID.

    Usage:
        cmd = GetSubjectCommand(client, "subj_abc123")
        result = cmd.execute()
        if result:
            subject = result.data['subject']
    """

    def __init__(self, client: IthAPIClient, subject_id: str, include_deleted: bool = False):
        """
        Initialize command.

        Args:
            client: ITH API client
            subject_id: Subject identifier
            include_deleted: Include if soft-deleted
        """
        super().__init__()
        self.client = client
        self.subject_id = subject_id
        self.include_deleted = include_deleted

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.subject_id:
            self.logger.error("subject_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute get subject command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: subject_id is required"
            )

        try:
            self.logger.info(f"Getting subject: {self.subject_id}")
            data = self.client.get_subject(self.subject_id, self.include_deleted)

            return CommandResult(
                success=True,
                data=data
            )
        except Exception as e:
            self.logger.error(f"Failed to get subject {self.subject_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class DownloadSubjectCommand(Command):
    """
    Download subject archive containing all sessions and scans.

    Usage:
        cmd = DownloadSubjectCommand(
            client,
            "subj_abc123",
            Path("/downloads/subject.zip"),
            compression_format="zip"
        )
        result = cmd.execute()
        if result:
            file_path = result.data['file_path']
    """

    def __init__(
        self,
        client: IthAPIClient,
        subject_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6
    ):
        """
        Initialize command.

        Args:
            client: ITH API client
            subject_id: Subject identifier
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
        """
        super().__init__()
        self.client = client
        self.subject_id = subject_id
        self.output_path = Path(output_path)
        self.compression_format = compression_format
        self.compression_level = compression_level

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.subject_id:
            self.logger.error("subject_id is required")
            return False

        if self.compression_format not in ['zip', 'tar.gz']:
            self.logger.error(f"Invalid compression format: {self.compression_format}")
            return False

        if not (0 <= self.compression_level <= 9):
            self.logger.error(f"Compression level must be 0-9, got: {self.compression_level}")
            return False

        return True

    def execute(self) -> CommandResult:
        """Execute download subject command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            self.logger.info(f"Downloading subject {self.subject_id} to {self.output_path}")

            file_path = self.client.download_subject(
                self.subject_id,
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
                    'subject_id': self.subject_id,
                    'compression_format': self.compression_format
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to download subject {self.subject_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )
