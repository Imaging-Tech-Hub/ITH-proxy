"""
Encrypted Django model fields for sensitive data.
"""
from django.db import models
from receiver.utils.encryption import encrypt_value, decrypt_value


class EncryptedCharField(models.CharField):
    """
    CharField that automatically encrypts/decrypts data.
    """
    description = "Encrypted CharField"

    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        if value is None or value == '':
            return value
        encrypted = encrypt_value(str(value))
        return encrypted

    def from_db_value(self, value, expression, connection):
        """Decrypt value when loading from database."""
        if value is None or value == '':
            return value
        return decrypt_value(value)

    def to_python(self, value):
        """Convert to Python type."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)


class EncryptedTextField(models.TextField):
    """
    TextField that automatically encrypts/decrypts data.
    """
    description = "Encrypted TextField"

    def get_prep_value(self, value):
        """Encrypt value before saving to database."""
        if value is None or value == '':
            return value
        encrypted = encrypt_value(str(value))
        return encrypted

    def from_db_value(self, value, expression, connection):
        """Decrypt value when loading from database."""
        if value is None or value == '':
            return value
        return decrypt_value(value)

    def to_python(self, value):
        """Convert to Python type."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)
