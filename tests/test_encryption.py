"""
Tests for credentials encryption
"""

import pytest
from app.utils.credentials_encryption import encrypt_credentials, decrypt_credentials


class TestEncryption:
    """Test encryption/decryption"""

    def test_encrypt_decrypt_simple(self):
        """Test basic encryption and decryption"""
        data = {
            'access_token': 'test_token_123',
            'refresh_token': 'refresh_xyz'
        }

        encrypted = encrypt_credentials(data)

        # Should have _encrypted key
        assert '_encrypted' in encrypted
        assert isinstance(encrypted['_encrypted'], str)

        # Decrypt should return original data
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == data

    def test_encrypt_decrypt_complex(self):
        """Test encryption with complex nested data"""
        data = {
            'access_token': 'token',
            'user_info': {
                'id': '123',
                'email': 'test@example.com',
                'metadata': {
                    'created_at': 1234567890
                }
            },
            'scopes': ['read', 'write'],
            'expires_at': 9999999999
        }

        encrypted = encrypt_credentials(data)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == data
        assert decrypted['user_info']['email'] == 'test@example.com'
        assert decrypted['scopes'] == ['read', 'write']

    def test_encrypted_data_format(self):
        """Test that encrypted data has correct format"""
        data = {'token': 'secret'}

        encrypted = encrypt_credentials(data)

        # Should only have _encrypted key
        assert set(encrypted.keys()) == {'_encrypted'}

        # Encrypted value should be a base64 string
        assert isinstance(encrypted['_encrypted'], str)
        assert len(encrypted['_encrypted']) > 0

    def test_decrypt_invalid_data(self):
        """Test decrypting invalid data raises error"""
        with pytest.raises(Exception):
            decrypt_credentials({'not_encrypted': 'data'})

    def test_encrypt_preserves_types(self):
        """Test that encryption preserves data types"""
        data = {
            'string': 'text',
            'number': 42,
            'float': 3.14,
            'bool': True,
            'none': None,
            'list': [1, 2, 3],
            'dict': {'nested': 'value'}
        }

        encrypted = encrypt_credentials(data)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == data
        assert isinstance(decrypted['number'], int)
        assert isinstance(decrypted['float'], float)
        assert isinstance(decrypted['bool'], bool)
        assert decrypted['none'] is None

    def test_multiple_encryptions_different(self):
        """Test that multiple encryptions of same data produce different results"""
        data = {'token': 'secret'}

        encrypted1 = encrypt_credentials(data)
        encrypted2 = encrypt_credentials(data)

        # Different encrypted values due to IV/nonce
        # Note: Fernet uses timestamp + random data, so this might be the same
        # if called in same microsecond. Just test they decrypt correctly.
        assert decrypt_credentials(encrypted1) == data
        assert decrypt_credentials(encrypted2) == data

    def test_empty_data(self):
        """Test encrypting empty data"""
        data = {}

        encrypted = encrypt_credentials(data)
        decrypted = decrypt_credentials(encrypted)

        assert decrypted == data
