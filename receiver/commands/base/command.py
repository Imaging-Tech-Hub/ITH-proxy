"""
Abstract base command class.
"""
from abc import ABC, abstractmethod
import logging
from .result import CommandResult


class Command(ABC):
    """
    Abstract base class for all commands following the Command Pattern.

    Commands encapsulate a single operation that can be executed,
    validated, and potentially undone.

    Example:
        class MyCommand(Command):
            def __init__(self, param: str):
                super().__init__()
                self.param = param

            def validate(self) -> bool:
                return bool(self.param)

            def execute(self) -> CommandResult:
                if not self.validate():
                    return CommandResult(success=False, error="Invalid parameters")

                try:
                    result = self._do_work()
                    return CommandResult(success=True, data=result)
                except Exception as e:
                    self.logger.error(f"Command failed: {e}")
                    return CommandResult(success=False, error=str(e))

            def _do_work(self):
                # Actual work here
                pass
    """

    def __init__(self):
        """Initialize command with logger."""
        self.logger = logging.getLogger(f'receiver.commands.{self.__class__.__name__}')

    @abstractmethod
    def execute(self) -> CommandResult:
        """
        Execute the command.

        Returns:
            CommandResult: Result of command execution

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    def validate(self) -> bool:
        """
        Validate command parameters before execution.

        Override this method to add validation logic specific to your command.

        Returns:
            bool: True if parameters are valid, False otherwise
        """
        return True

    def undo(self) -> CommandResult:
        """
        Undo the command (optional - override if needed).

        Returns:
            CommandResult: Result of undo operation
        """
        return CommandResult(
            success=False,
            error=f"Undo not implemented for {self.__class__.__name__}"
        )

    def __str__(self) -> str:
        """String representation of command."""
        return f"{self.__class__.__name__}"

    def __repr__(self) -> str:
        """Detailed representation of command."""
        return f"<{self.__class__.__name__} at {hex(id(self))}>"
