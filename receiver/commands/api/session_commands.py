"""
Session-related commands for ITH API.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from receiver.commands.base import Command, CommandResult
from receiver.services.api import IthAPIClient


class ListSessionsCommand(Command):
    """
    List all sessions in workspace with optional filters.

    Usage:
        cmd = ListSessionsCommand(client, subject_id="subj_abc", modality="MR")
        result = cmd.execute()
        if result:
            sessions = result.data['sessions']
    """

    def __init__(self, client: IthAPIClient, **filters):
        """
        Initialize command.

        Args:
            client: ITH API client
            **filters: Optional filters (subject_id, modality, etc.)
        """
        super().__init__()
        self.client = client
        self.filters = filters

    def execute(self) -> CommandResult:
        """Execute list sessions command."""
        try:
            self.logger.info(f"Listing sessions with filters: {self.filters}")
            data = self.client.list_sessions(**self.filters)

            sessions_count = len(data.get('sessions', []))
            self.logger.info(f"Found {sessions_count} sessions")

            return CommandResult(
                success=True,
                data=data,
                metadata={'count': sessions_count}
            )
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class GetSessionCommand(Command):
    """
    Get specific session by ID.

    Usage:
        cmd = GetSessionCommand(client, "sess_def456")
        result = cmd.execute()
        if result:
            session = result.data['session']
    """

    def __init__(self, client: IthAPIClient, session_id: str, include_deleted: bool = False):
        """
        Initialize command.

        Args:
            client: ITH API client
            session_id: Session identifier
            include_deleted: Include if soft-deleted
        """
        super().__init__()
        self.client = client
        self.session_id = session_id
        self.include_deleted = include_deleted

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.session_id:
            self.logger.error("session_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute get session command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: session_id is required"
            )

        try:
            self.logger.info(f"Getting session: {self.session_id}")
            data = self.client.get_session(self.session_id, self.include_deleted)

            return CommandResult(
                success=True,
                data=data
            )
        except Exception as e:
            self.logger.error(f"Failed to get session {self.session_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class DownloadSessionCommand(Command):
    """
    Download session archive containing all scans.

    Usage:
        cmd = DownloadSessionCommand(
            client,
            "sess_def456",
            "subj_abc123",
            Path("/downloads/session.zip")
        )
        result = cmd.execute()
        if result:
            file_path = result.data['file_path']
    """

    def __init__(
        self,
        client: IthAPIClient,
        session_id: str,
        subject_id: str,
        output_path: Path,
        compression_format: str = 'zip',
        compression_level: int = 6
    ):
        """
        Initialize command.

        Args:
            client: ITH API client
            session_id: Session identifier
            subject_id: Parent subject ID
            output_path: Path to save archive
            compression_format: zip or tar.gz
            compression_level: 0-9
        """
        super().__init__()
        self.client = client
        self.session_id = session_id
        self.subject_id = subject_id
        self.output_path = Path(output_path)
        self.compression_format = compression_format
        self.compression_level = compression_level

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.session_id:
            self.logger.error("session_id is required")
            return False

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
        """Execute download session command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            self.logger.info(f"Downloading session {self.session_id} to {self.output_path}")

            file_path = self.client.download_session(
                self.session_id,
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
                    'session_id': self.session_id,
                    'subject_id': self.subject_id,
                    'compression_format': self.compression_format
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to download session {self.session_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )
