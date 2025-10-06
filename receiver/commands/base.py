"""
Base Command Pattern implementation.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger('receiver.commands')


@dataclass
class CommandResult:
    """
    Result of command execution.
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __bool__(self):
        """Allow result to be used in boolean context."""
        return self.success


class Command(ABC):
    """
    Abstract base class for all commands.

    Commands encapsulate a single operation that can be executed,
    undone, and composed with other commands.
    """

    def __init__(self):
        """Initialize command."""
        self.logger = logging.getLogger(f'receiver.commands.{self.__class__.__name__}')

    @abstractmethod
    def execute(self) -> CommandResult:
        """
        Execute the command.

        Returns:
            CommandResult: Result of command execution
        """
        pass

    def undo(self) -> CommandResult:
        """
        Undo the command (optional - override if needed).

        Returns:
            CommandResult: Result of undo operation
        """
        return CommandResult(
            success=False,
            error="Undo not implemented for this command"
        )

    def validate(self) -> bool:
        """
        Validate command parameters before execution.

        Returns:
            bool: True if valid, False otherwise
        """
        return True

    def __str__(self):
        """String representation of command."""
        return f"{self.__class__.__name__}"
