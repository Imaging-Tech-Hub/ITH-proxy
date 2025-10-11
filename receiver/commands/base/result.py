"""
Command execution result.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Dict


@dataclass
class CommandResult:
    """
    Result of command execution.

    Attributes:
        success: Whether the command executed successfully
        data: Result data (if any)
        error: Error message (if failed)
        metadata: Additional metadata about the execution
    """
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow result to be used in boolean context."""
        return self.success

    def __repr__(self) -> str:
        """String representation of result."""
        status = "SUCCESS" if self.success else "FAILED"
        if self.error:
            return f"CommandResult({status}, error='{self.error}')"
        return f"CommandResult({status})"
