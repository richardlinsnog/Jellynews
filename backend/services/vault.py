

from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class SecretsVaultService:
    """Encrypt/decrypt secrets at rest using Fernet symmetric encryption.

    Key derivation priority:
    1. SECRETS_ENCRYPTION_KEY env var, if set (must be 32 bytes, base64-encoded)
    2. Derived from APP_SECRET_KEY + salt via PBKDF2 (always available)
    """

    _instance: Optional[SecretsVaultService] = None
    _fernet: Optional[Fernet] = None

    def __new__(cls) -> SecretsVaultService:
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
        return cls._instance

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = self._build_fernet()
        return self._fernet

    def _build_fernet(self) -> Fernet:
        if settings.SECRETS_ENCRYPTION_KEY:
            key = settings.SECRETS_ENCRYPTION_KEY.encode()
            logger.info("secrets_vault_key_source", source="env_var")
        else:
            key = self._derive_key()
            logger.info("secrets_vault_key_source", source="pbkdf2_derived")

        # Fernet requires 32 url-safe base64 bytes
        if len(key) == 32 and not self._is_base64_urlsafe(key):
            key = base64.urlsafe_b64encode(key)

        return Fernet(key)

    def _derive_key(self) -> bytes:
        salt = hashlib.sha256(b"jellynews-vault-salt").digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        derived = kdf.derive(settings.APP_SECRET_KEY.encode())
        return base64.urlsafe_b64encode(derived)

    @staticmethod
    def _is_base64_urlsafe(data: bytes) -> bool:
        try:
            decoded = base64.urlsafe_b64decode(data)
            return base64.urlsafe_b64encode(decoded) == data
        except Exception:
            return False

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext value and return base64 token."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        """Decrypt a base64 token back to plaintext."""
        return self.fernet.decrypt(token.encode()).decode()


def get_vault() -> SecretsVaultService:
    return SecretsVaultService()

