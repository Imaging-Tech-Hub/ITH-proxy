"""
DICOM verification commands.
"""
from receiver.commands.base import Command, CommandResult
from receiver.utils.config import NodeConfig
from .services import DICOMVerificationService


class VerifyNodeConnectionCommand(Command):
    """
    Verify connection to PACS node using C-ECHO.

    Refactored version with service layer separation.

    Example:
        node = NodeConfig(node_id="n1", name="PACS", ae_title="PACS", host="10.0.1.100", port=11112)
        cmd = VerifyNodeConnectionCommand(node)
        result = cmd.execute()
        if result:
            print(f"Node {node.name} is online")
    """

    def __init__(self, node: NodeConfig, ae_title: str = 'DICOM_PROXY'):
        """
        Initialize command.

        Args:
            node: PACS node to verify
            ae_title: AE Title for verification
        """
        super().__init__()
        self.node = node
        self.service = DICOMVerificationService(ae_title)

    def execute(self) -> CommandResult:
        """Execute verification command."""
        try:
            self.logger.info(f"Verifying connection to {self.node.name}")

            is_online = self.service.verify_connection(self.node)

            if is_online:
                return CommandResult(
                    success=True,
                    data={'is_online': True},
                    metadata={'node': self.node.name}
                )
            else:
                return CommandResult(
                    success=False,
                    data={'is_online': False},
                    error=f"Node {self.node.name} is offline"
                )

        except Exception as e:
            self.logger.error(f"Failed to verify connection to {self.node.name}: {e}")
            return CommandResult(
                success=False,
                data={'is_online': False},
                error=str(e)
            )
