"""
DICOM verification service - handles connection verification via C-ECHO.
"""
import logging
from receiver.services.coordination import DICOMServiceUser
from receiver.utils.config import NodeConfig


logger = logging.getLogger('receiver.commands.dicom.verification_service')


class DICOMVerificationService:
    """
    Service for verifying DICOM node connectivity using C-ECHO.

    Separates business logic from command execution.
    """

    def __init__(self, ae_title: str = 'DICOM_PROXY'):
        """
        Initialize verification service.

        Args:
            ae_title: AE Title for verification requests
        """
        self.ae_title = ae_title
        self.logger = logger

    def verify_connection(self, node: NodeConfig) -> bool:
        """
        Verify connection to a PACS node using C-ECHO.

        Args:
            node: Node to verify

        Returns:
            bool: True if node is reachable, False otherwise
        """
        scu = DICOMServiceUser(
            ae_title=self.ae_title,
            max_pdu_size=node.max_pdu_size,
            connection_timeout=node.connection_timeout,
            verification_only=True
        )

        try:
            is_online = scu.verify_connection(
                node.host,
                node.port,
                node.ae_title
            )

            if is_online:
                self.logger.info(f"Connection verified to {node.name}")
            else:
                self.logger.warning(f"Connection failed to {node.name}")

            return is_online

        except Exception as e:
            self.logger.error(f"Error verifying connection to {node.name}: {e}")
            return False
