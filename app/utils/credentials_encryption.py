"""
Credentials Encryption Service
AES-256 encryption for storing sensitive credentials (OAuth tokens, API keys, etc)
Based on Activepieces architecture
"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from typing import Dict, Any, Optional


class CredentialsEncryption:
    """
    Handles encryption/decryption of credentials
    Uses AES-256 via Fernet (symmetric encryption)
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize with encryption key from environment

        Args:
            encryption_key: Base64-encoded 32-byte key. If None, uses INTEGRATION_ENCRYPTION_KEY env var
        """
        if encryption_key is None:
            encryption_key = os.getenv('INTEGRATION_ENCRYPTION_KEY')

        if not encryption_key:
            raise ValueError("INTEGRATION_ENCRYPTION_KEY environment variable is required")

        # If key is hex string (64 chars), convert to bytes
        if len(encryption_key) == 64:
            # Hex string - convert to bytes
            key_bytes = bytes.fromhex(encryption_key)
        else:
            # Assume base64-encoded
            key_bytes = base64.urlsafe_b64decode(encryption_key)

        # Derive Fernet key from provided key
        if len(key_bytes) != 32:
            # Use PBKDF2HMAC to derive 32-byte key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'pipehub_salt',  # Fixed salt for key derivation
                iterations=100000,
                backend=default_backend()
            )
            key_bytes = kdf.derive(key_bytes)

        # Create Fernet instance
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self.cipher = Fernet(fernet_key)

    def encrypt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt credentials dictionary

        Args:
            data: Plain credentials dict (e.g., {access_token: "...", refresh_token: "..."})

        Returns:
            Encrypted credentials as JSONB-compatible dict
        """
        # Convert to JSON string
        json_str = json.dumps(data)

        # Encrypt
        encrypted_bytes = self.cipher.encrypt(json_str.encode('utf-8'))

        # Return as base64 string in a dict (for JSONB compatibility)
        return {
            '_encrypted': base64.b64encode(encrypted_bytes).decode('utf-8')
        }

    def decrypt(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt credentials dictionary

        Args:
            encrypted_data: Encrypted credentials from database (must have '_encrypted' key)

        Returns:
            Decrypted credentials dict
        """
        if not isinstance(encrypted_data, dict) or '_encrypted' not in encrypted_data:
            # Not encrypted or wrong format - return as-is (backward compatibility)
            return encrypted_data

        # Get encrypted bytes
        encrypted_b64 = encrypted_data['_encrypted']
        encrypted_bytes = base64.b64decode(encrypted_b64)

        # Decrypt
        decrypted_bytes = self.cipher.decrypt(encrypted_bytes)

        # Parse JSON
        json_str = decrypted_bytes.decode('utf-8')
        return json.loads(json_str)

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key (64-char hex string)
        Use this for INTEGRATION_ENCRYPTION_KEY in .env

        Returns:
            64-character hexadecimal string (32 bytes)
        """
        key = Fernet.generate_key()
        # Decode base64 to get raw bytes
        key_bytes = base64.urlsafe_b64decode(key)
        # Return as hex string
        return key_bytes.hex()


# Singleton instance
_encryption_service: Optional[CredentialsEncryption] = None


def get_encryption_service() -> CredentialsEncryption:
    """Get singleton encryption service"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = CredentialsEncryption()
    return _encryption_service


def encrypt_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt credentials (convenience function)"""
    service = get_encryption_service()
    return service.encrypt(credentials)


def decrypt_credentials(encrypted_credentials: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt credentials (convenience function)"""
    service = get_encryption_service()
    return service.decrypt(encrypted_credentials)


# CLI tool to generate key
if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'generate-key':
        key = CredentialsEncryption.generate_key()
        print(f"Generated encryption key:\n{key}")
        print(f"\nAdd to .env:")
        print(f"INTEGRATION_ENCRYPTION_KEY={key}")
    else:
        print("Usage: python credentials_encryption.py generate-key")
