"""
Testes unitários para adapters de assinatura.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.integrations.signature.clicksign import ClickSignAdapter
from app.services.integrations.signature.zapsign import ZapSignAdapter
from app.services.integrations.signature.factory import SignatureProviderFactory
from app.services.integrations.signature.base import SignatureStatus
from app.models import DataSourceConnection, GeneratedDocument


class TestClickSignAdapter:
    """Testes para ClickSignAdapter"""
    
    @patch('app.services.integrations.signature.clicksign.DataSourceConnection')
    def test_create_envelope(self, mock_connection):
        """Testa criação de envelope"""
        # Mock connection
        mock_conn = Mock()
        mock_conn.get_decrypted_credentials.return_value = {'api_key': 'test-key'}
        mock_conn.config = {'environment': 'sandbox'}
        mock_connection.query.filter_by.return_value.first_or_404.return_value = mock_conn
        
        adapter = ClickSignAdapter('org-id', 'conn-id')
        adapter.api_key = 'test-key'
        adapter.base_url = 'https://sandbox.clicksign.com/api/v3'
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'data': {'id': 'env-123'}}
            mock_response.ok = True
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            envelope_id = adapter.create_envelope('Test Envelope')
            
            assert envelope_id == 'env-123'
            mock_post.assert_called_once()
    
    @patch('app.services.integrations.signature.clicksign.DataSourceConnection')
    def test_get_status_mapping(self, mock_connection):
        """Testa mapeamento de status"""
        mock_conn = Mock()
        mock_conn.get_decrypted_credentials.return_value = {'api_key': 'test-key'}
        mock_conn.config = {'environment': 'sandbox'}
        mock_connection.query.filter_by.return_value.first_or_404.return_value = mock_conn
        
        adapter = ClickSignAdapter('org-id', 'conn-id')
        adapter.api_key = 'test-key'
        adapter.base_url = 'https://sandbox.clicksign.com/api/v3'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'data': {'attributes': {'status': 'running'}}
            }
            mock_response.ok = True
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            status = adapter.get_status('env-123')
            assert status == SignatureStatus.SENT


class TestZapSignAdapter:
    """Testes para ZapSignAdapter"""
    
    @patch('app.services.integrations.signature.zapsign.DataSourceConnection')
    def test_create_envelope(self, mock_connection):
        """Testa criação de documento"""
        mock_conn = Mock()
        mock_conn.get_decrypted_credentials.return_value = {'api_token': 'test-token'}
        mock_connection.query.filter_by.return_value.first_or_404.return_value = mock_conn
        
        adapter = ZapSignAdapter('org-id', 'conn-id')
        adapter.api_token = 'test-token'
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {'id': 'doc-123'}
            mock_response.ok = True
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            doc_id = adapter.create_envelope('Test Document')
            
            assert doc_id == 'doc-123'
            mock_post.assert_called_once()


class TestSignatureProviderFactory:
    """Testes para SignatureProviderFactory"""
    
    def test_list_providers(self):
        """Testa listagem de providers"""
        providers = SignatureProviderFactory.list_providers()
        assert 'clicksign' in providers
        assert 'zapsign' in providers
    
    def test_is_provider_supported(self):
        """Testa verificação de provider suportado"""
        assert SignatureProviderFactory.is_provider_supported('clicksign') is True
        assert SignatureProviderFactory.is_provider_supported('zapsign') is True
        assert SignatureProviderFactory.is_provider_supported('invalid') is False
    
    @patch('app.services.integrations.signature.clicksign.DataSourceConnection')
    def test_get_adapter_clicksign(self, mock_connection):
        """Testa criação de adapter ClickSign"""
        mock_conn = Mock()
        mock_conn.get_decrypted_credentials.return_value = {'api_key': 'test-key'}
        mock_conn.config = {'environment': 'sandbox'}
        mock_connection.query.filter_by.return_value.first_or_404.return_value = mock_conn
        
        adapter = SignatureProviderFactory.get_adapter(
            provider='clicksign',
            connection_id='conn-id',
            organization_id='org-id'
        )
        
        assert isinstance(adapter, ClickSignAdapter)
    
    @patch('app.services.integrations.signature.zapsign.DataSourceConnection')
    def test_get_adapter_zapsign(self, mock_connection):
        """Testa criação de adapter ZapSign"""
        mock_conn = Mock()
        mock_conn.get_decrypted_credentials.return_value = {'api_token': 'test-token'}
        mock_connection.query.filter_by.return_value.first_or_404.return_value = mock_conn
        
        adapter = SignatureProviderFactory.get_adapter(
            provider='zapsign',
            connection_id='conn-id',
            organization_id='org-id'
        )
        
        assert isinstance(adapter, ZapSignAdapter)
    
    def test_get_adapter_invalid(self):
        """Testa provider inválido"""
        with pytest.raises(ValueError):
            SignatureProviderFactory.get_adapter(
                provider='invalid',
                connection_id='conn-id',
                organization_id='org-id'
            )
