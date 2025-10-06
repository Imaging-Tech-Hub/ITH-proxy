"""
Archive-related commands for Laminate API.
"""
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from .base import Command, CommandResult
from receiver.services.laminate_api_client import LaminateAPIClient


class CreateArchiveCommand(Command):
    """
    Create custom archive with selected entities.

    Usage:
        entity_selections = [
            {"entity_type": "subject", "entity_id": "subj_abc"},
            {"entity_type": "session", "entity_id": "sess_def", "parent_ids": {"subject_id": "subj_abc"}}
        ]
        cmd = CreateArchiveCommand(client, "my-archive", entity_selections)
        result = cmd.execute()
        if result:
            archive_id = result.data['archive_id']
    """

    def __init__(
        self,
        client: LaminateAPIClient,
        archive_name: str,
        entity_selections: List[Dict[str, Any]],
        compression_format: str = 'zip',
        compression_level: int = 6
    ):
        """
        Initialize command.

        Args:
            client: Laminate API client
            archive_name: Name for the archive
            entity_selections: List of entities to include
            compression_format: zip or tar.gz
            compression_level: 0-9
        """
        super().__init__()
        self.client = client
        self.archive_name = archive_name
        self.entity_selections = entity_selections
        self.compression_format = compression_format
        self.compression_level = compression_level

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.archive_name:
            self.logger.error("archive_name is required")
            return False

        if not self.entity_selections:
            self.logger.error("entity_selections cannot be empty")
            return False

        if self.compression_format not in ['zip', 'tar.gz']:
            self.logger.error(f"Invalid compression format: {self.compression_format}")
            return False

        if not (0 <= self.compression_level <= 9):
            self.logger.error(f"Compression level must be 0-9, got: {self.compression_level}")
            return False

        return True

    def execute(self) -> CommandResult:
        """Execute create archive command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            self.logger.info(f"Creating archive '{self.archive_name}' with {len(self.entity_selections)} entities")

            data = self.client.create_archive(
                self.archive_name,
                self.entity_selections,
                self.compression_format,
                self.compression_level
            )

            archive_id = data.get('archive_id')
            self.logger.info(f"Archive created with ID: {archive_id}")

            return CommandResult(
                success=True,
                data=data,
                metadata={
                    'archive_name': self.archive_name,
                    'entity_count': len(self.entity_selections)
                }
            )
        except Exception as e:
            self.logger.error(f"Failed to create archive: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class GetArchiveStatusCommand(Command):
    """
    Get status of an archive creation job.

    Usage:
        cmd = GetArchiveStatusCommand(client, "arch_jkl012")
        result = cmd.execute()
        if result:
            status = result.data['archive']['status']  # processing, completed, failed, expired
    """

    def __init__(self, client: LaminateAPIClient, archive_id: str):
        """
        Initialize command.

        Args:
            client: Laminate API client
            archive_id: Archive identifier
        """
        super().__init__()
        self.client = client
        self.archive_id = archive_id

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.archive_id:
            self.logger.error("archive_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute get archive status command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: archive_id is required"
            )

        try:
            self.logger.info(f"Getting status for archive: {self.archive_id}")
            data = self.client.get_archive_status(self.archive_id)

            archive_status = data.get('archive', {}).get('status')
            self.logger.info(f"Archive status: {archive_status}")

            return CommandResult(
                success=True,
                data=data,
                metadata={'status': archive_status}
            )
        except Exception as e:
            self.logger.error(f"Failed to get archive status {self.archive_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class DownloadArchiveCommand(Command):
    """
    Download completed archive.

    Usage:
        cmd = DownloadArchiveCommand(client, "arch_jkl012", Path("/downloads/archive.zip"))
        result = cmd.execute()
        if result:
            file_path = result.data['file_path']
    """

    def __init__(
        self,
        client: LaminateAPIClient,
        archive_id: str,
        output_path: Path
    ):
        """
        Initialize command.

        Args:
            client: Laminate API client
            archive_id: Archive identifier
            output_path: Path to save archive
        """
        super().__init__()
        self.client = client
        self.archive_id = archive_id
        self.output_path = Path(output_path)

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.archive_id:
            self.logger.error("archive_id is required")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute download archive command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed: archive_id is required"
            )

        try:
            self.logger.info(f"Downloading archive {self.archive_id} to {self.output_path}")

            file_path = self.client.download_archive(
                self.archive_id,
                self.output_path
            )

            file_size = file_path.stat().st_size
            self.logger.info(f"Download complete: {file_size} bytes")

            return CommandResult(
                success=True,
                data={
                    'file_path': str(file_path),
                    'file_size': file_size
                },
                metadata={'archive_id': self.archive_id}
            )
        except Exception as e:
            self.logger.error(f"Failed to download archive {self.archive_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )


class WaitForArchiveCommand(Command):
    """
    Wait for archive to complete and optionally download it.

    Usage:
        cmd = WaitForArchiveCommand(
            client,
            "arch_jkl012",
            timeout=300,
            poll_interval=5,
            download_path=Path("/downloads/archive.zip")  # optional
        )
        result = cmd.execute()
        if result:
            if result.metadata['downloaded']:
                file_path = result.data['file_path']
    """

    def __init__(
        self,
        client: LaminateAPIClient,
        archive_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
        download_path: Optional[Path] = None
    ):
        """
        Initialize command.

        Args:
            client: Laminate API client
            archive_id: Archive identifier
            timeout: Max time to wait in seconds
            poll_interval: Time between status checks in seconds
            download_path: Optional path to download archive when complete
        """
        super().__init__()
        self.client = client
        self.archive_id = archive_id
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.download_path = Path(download_path) if download_path else None

    def validate(self) -> bool:
        """Validate command parameters."""
        if not self.archive_id:
            self.logger.error("archive_id is required")
            return False
        if self.timeout <= 0:
            self.logger.error(f"Invalid timeout: {self.timeout}")
            return False
        if self.poll_interval <= 0:
            self.logger.error(f"Invalid poll_interval: {self.poll_interval}")
            return False
        return True

    def execute(self) -> CommandResult:
        """Execute wait for archive command."""
        if not self.validate():
            return CommandResult(
                success=False,
                error="Validation failed"
            )

        try:
            self.logger.info(f"Waiting for archive {self.archive_id} (timeout: {self.timeout}s)")
            start_time = time.time()

            while time.time() - start_time < self.timeout:
                status_result = GetArchiveStatusCommand(self.client, self.archive_id).execute()

                if not status_result:
                    return status_result

                archive_status = status_result.data.get('archive', {}).get('status')

                if archive_status == 'completed':
                    self.logger.info("Archive completed")

                    if self.download_path:
                        download_result = DownloadArchiveCommand(
                            self.client,
                            self.archive_id,
                            self.download_path
                        ).execute()

                        if not download_result:
                            return download_result

                        return CommandResult(
                            success=True,
                            data=download_result.data,
                            metadata={
                                'status': 'completed',
                                'downloaded': True,
                                'wait_time': time.time() - start_time
                            }
                        )
                    else:
                        return CommandResult(
                            success=True,
                            data=status_result.data,
                            metadata={
                                'status': 'completed',
                                'downloaded': False,
                                'wait_time': time.time() - start_time
                            }
                        )

                elif archive_status == 'failed':
                    self.logger.error("Archive creation failed")
                    return CommandResult(
                        success=False,
                        error="Archive creation failed"
                    )

                elif archive_status == 'expired':
                    self.logger.error("Archive has expired")
                    return CommandResult(
                        success=False,
                        error="Archive has expired"
                    )

                self.logger.debug(f"Archive status: {archive_status}, waiting {self.poll_interval}s...")
                time.sleep(self.poll_interval)

            self.logger.error(f"Timeout waiting for archive (>{self.timeout}s)")
            return CommandResult(
                success=False,
                error=f"Timeout waiting for archive after {self.timeout}s"
            )

        except Exception as e:
            self.logger.error(f"Failed waiting for archive {self.archive_id}: {e}")
            return CommandResult(
                success=False,
                error=str(e)
            )
