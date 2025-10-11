"""
DICOM send service - encapsulates business logic for sending DICOM files.
"""
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from receiver.services.coordination import DICOMServiceUser, DICOMSendResult
from receiver.utils.config import NodeConfig


logger = logging.getLogger('receiver.commands.dicom.send_service')


@dataclass
class SendOptions:
    """Configuration options for DICOM send operation."""
    recursive: bool = True
    retry_count: int = 3
    retry_delay: int = 5
    ae_title: str = 'DICOM_PROXY'


class DICOMSendService:
    """
    Service for sending DICOM files to PACS nodes.

    Separates business logic from command execution.
    """

    def __init__(self, options: Optional[SendOptions] = None):
        """
        Initialize send service.

        Args:
            options: Send configuration options
        """
        self.options = options or SendOptions()
        self.logger = logger

    def send_to_node(
        self,
        node: NodeConfig,
        files: Optional[List[Path]] = None,
        directory: Optional[Path] = None
    ) -> DICOMSendResult:
        """
        Send DICOM files to a single node.

        Args:
            node: Target PACS node
            files: List of DICOM files (if sending specific files)
            directory: Directory containing DICOM files (if sending directory)

        Returns:
            DICOMSendResult: Result of send operation

        Raises:
            ValueError: If both files and directory are provided, or neither
        """
        if (files and directory) or (not files and not directory):
            raise ValueError("Provide either files or directory, not both or neither")

        scu = self._create_scu(node)

        try:
            if files:
                return scu.send_files(
                    files,
                    node.host,
                    node.port,
                    node.ae_title,
                    retry_count=node.retry_count,
                    retry_delay=node.retry_delay
                )
            else:
                return scu.send_directory(
                    directory,
                    node.host,
                    node.port,
                    node.ae_title,
                    recursive=self.options.recursive,
                    retry_count=node.retry_count,
                    retry_delay=node.retry_delay
                )
        except Exception as e:
            self.logger.error(f"Failed to send DICOM to {node.name}: {e}")
            raise

    def _create_scu(self, node: NodeConfig) -> DICOMServiceUser:
        """
        Create DICOM SCU client.

        Args:
            node: Node configuration

        Returns:
            DICOMServiceUser: Configured SCU client
        """
        return DICOMServiceUser(
            ae_title=self.options.ae_title,
            max_pdu_size=node.max_pdu_size,
            connection_timeout=node.connection_timeout
        )
