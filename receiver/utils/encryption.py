"""
Field-level encryption utilities for sensitive PHI data.
Uses Fernet symmetric encryption from cryptography library.
"""
import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings


class EncryptionManager:
    """
    Manages encryption/decryption of sensitive data using Fernet symmetric encryption.
    """
    _instance: Optional['EncryptionManager'] = None
    _fernet: Optional[Fernet] = None

    def __new__(cls):
        """Singleton pattern to ensure single encryption key instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Fernet cipher with encryption key."""
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)

    def _get_or_create_key(self) -> bytes:
        """
        Get encryption key from settings or environment.
        In production, this should come from a secure key management system.
        """
        key_str = os.getenv('ENCRYPTION_KEY')

        if key_str:
            return key_str.encode()

        secret_key = settings.SECRET_KEY.encode()
        salt = b'phi_encryption_salt_v1'

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key))
        return key

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ''

        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ''

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")


_encryption_manager = EncryptionManager()


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    return _encryption_manager.encrypt(value)


def decrypt_value(value: str) -> str:
    """Decrypt a string value."""
    return _encryption_manager.decrypt(value)
