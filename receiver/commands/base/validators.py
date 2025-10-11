"""
Reusable validation utilities for command parameters.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Union


class Validator(ABC):
    """
    Abstract base class for validators.
    """

    @abstractmethod
    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a value.

        Args:
            value: Value to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        pass

    def __call__(self, value: Any) -> tuple[bool, Optional[str]]:
        """Allow validator to be called as a function."""
        return self.validate(value)


class RequiredFieldValidator(Validator):
    """
    Validates that a field is not None or empty.

    Example:
        validator = RequiredFieldValidator("subject_id")
        is_valid, error = validator.validate("abc123")
    """

    def __init__(self, field_name: str):
        """
        Initialize validator.

        Args:
            field_name: Name of the field being validated
        """
        self.field_name = field_name

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate that value is not empty."""
        if value is None:
            return False, f"{self.field_name} is required"

        if isinstance(value, str) and not value.strip():
            return False, f"{self.field_name} cannot be empty"

        if isinstance(value, (list, dict, set)) and len(value) == 0:
            return False, f"{self.field_name} cannot be empty"

        return True, None


class PathExistsValidator(Validator):
    """
    Validates that a path exists on the filesystem.

    Example:
        validator = PathExistsValidator("input_directory", must_be_dir=True)
        is_valid, error = validator.validate(Path("/path/to/dir"))
    """

    def __init__(self, field_name: str, must_be_dir: bool = False, must_be_file: bool = False):
        """
        Initialize validator.

        Args:
            field_name: Name of the field being validated
            must_be_dir: Require path to be a directory
            must_be_file: Require path to be a file
        """
        self.field_name = field_name
        self.must_be_dir = must_be_dir
        self.must_be_file = must_be_file

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate that path exists."""
        if value is None:
            return False, f"{self.field_name} is required"

        path = Path(value) if not isinstance(value, Path) else value

        if not path.exists():
            return False, f"{self.field_name} does not exist: {path}"

        if self.must_be_dir and not path.is_dir():
            return False, f"{self.field_name} must be a directory: {path}"

        if self.must_be_file and not path.is_file():
            return False, f"{self.field_name} must be a file: {path}"

        return True, None


class ChoiceValidator(Validator):
    """
    Validates that a value is one of the allowed choices.

    Example:
        validator = ChoiceValidator("format", ["zip", "tar.gz"])
        is_valid, error = validator.validate("zip")
    """

    def __init__(self, field_name: str, choices: List[Any]):
        """
        Initialize validator.

        Args:
            field_name: Name of the field being validated
            choices: List of allowed values
        """
        self.field_name = field_name
        self.choices = choices

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate that value is in choices."""
        if value not in self.choices:
            choices_str = ", ".join(str(c) for c in self.choices)
            return False, f"{self.field_name} must be one of: {choices_str}, got: {value}"

        return True, None


class RangeValidator(Validator):
    """
    Validates that a numeric value is within a specified range.

    Example:
        validator = RangeValidator("compression_level", min_val=0, max_val=9)
        is_valid, error = validator.validate(5)
    """

    def __init__(
        self,
        field_name: str,
        min_val: Optional[Union[int, float]] = None,
        max_val: Optional[Union[int, float]] = None
    ):
        """
        Initialize validator.

        Args:
            field_name: Name of the field being validated
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
        """
        self.field_name = field_name
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate that value is in range."""
        if not isinstance(value, (int, float)):
            return False, f"{self.field_name} must be numeric, got: {type(value).__name__}"

        if self.min_val is not None and value < self.min_val:
            return False, f"{self.field_name} must be >= {self.min_val}, got: {value}"

        if self.max_val is not None and value > self.max_val:
            return False, f"{self.field_name} must be <= {self.max_val}, got: {value}"

        return True, None


class CompositeValidator(Validator):
    """
    Combines multiple validators with AND logic.

    Example:
        validator = CompositeValidator([
            RequiredFieldValidator("path"),
            PathExistsValidator("path", must_be_dir=True)
        ])
        is_valid, error = validator.validate(Path("/some/path"))
    """

    def __init__(self, validators: List[Validator]):
        """
        Initialize composite validator.

        Args:
            validators: List of validators to apply
        """
        self.validators = validators

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate using all validators."""
        for validator in self.validators:
            is_valid, error = validator.validate(value)
            if not is_valid:
                return False, error

        return True, None


def validate_all(validations: dict[str, tuple[Any, List[Validator]]]) -> tuple[bool, Optional[str]]:
    """
    Validate multiple fields at once.

    Args:
        validations: Dictionary mapping field names to (value, validators) tuples

    Returns:
        tuple: (all_valid, first_error_message)

    Example:
        is_valid, error = validate_all({
            'subject_id': (subject_id, [RequiredFieldValidator('subject_id')]),
            'output_path': (output_path, [
                RequiredFieldValidator('output_path'),
                PathExistsValidator('output_path', must_be_dir=True)
            ])
        })
    """
    for field_name, (value, validators) in validations.items():
        for validator in validators:
            is_valid, error = validator.validate(value)
            if not is_valid:
                return False, error

    return True, None
