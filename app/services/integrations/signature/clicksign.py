"""
Adapter para integração com ClickSign.
"""
from typing import Dict, Any, List, Optional
from app.services.integrations.signature.base import SignatureProviderAdapter, SignatureStatus
from app.models import DataSourceConnection
import requests
import logging

logger = logging.getLogger(__name__)

class ClickSignAdapter(SignatureProviderAdapter):
    """Adapter para ClickSign"""
    
    def __init__(self, organization_id: str, connection_id: str):
        self.api_key = None
        self.base_url = None
        super().__init__(organization_id, connection_id)
    
    def _load_connection(self):
        """Carrega conexão ClickSign"""
        connection = DataSourceConnection.query.filter_by(
            id=self.connection_id,
            organization_id=self.organization_id,
            source_type='clicksign',
            status='active'
        ).first_or_404()
        
        credentials = connection.get_decrypted_credentials()
        self.api_key = credentials.get('api_key') or credentials.get('clicksign_api_key')
        
        if not self.api_key:
            raise ValueError("API Key do ClickSign não configurada")
        
        # Determinar ambiente
        environment = connection.config.get('environment', 'sandbox') if connection.config else 'sandbox'
        if environment == 'production':
            self.base_url = "https://app.clicksign.com/api/v3"
        else:
            self.base_url = "https://sandbox.clicksign.com/api/v3"
    
    def test_connection(self) -> Dict[str, Any]:
        """Testa conexão com ClickSign"""
        try:
            response = requests.get(
                f"{self.base_url}/envelopes",
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json"
                },
                params={"page": 1, "per_page": 1},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'valid': True,
                    'message': 'Conexão válida',
                    'provider_info': response.json()
                }
            elif response.status_code == 401:
                return {
                    'valid': False,
                    'message': 'API key inválida ou expirada'
                }
            else:
                return {
                    'valid': False,
                    'message': f'Erro ao testar conexão: {response.status_code}'
                }
        except Exception as e:
            return {
                'valid': False,
                'message': f'Erro de conexão: {str(e)}'
            }
    
    def create_envelope(self, name: str) -> str:
        """Cria envelope no ClickSign"""
        url = f"{self.base_url}/envelopes"
        payload = {
            "data": {
                "type": "envelopes",
                "attributes": {
                    "name": name
                }
            }
        }
        
        response = requests.post(
            url,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
        data = response.json()
        return data.get('data', {}).get('id')
    
    def upload_document(self, envelope_id: str, file_bytes: bytes, filename: str) -> str:
        """Upload de documento para ClickSign"""
        url = f"{self.base_url}/envelopes/{envelope_id}/documents"
        
        files = {
            'file': (filename, file_bytes, 'application/pdf')
        }
        data = {
            'filename': filename
        }
        
        response = requests.post(
            url,
            headers={"Authorization": self.api_key},
            files=files,
            data=data
        )
        
        response.raise_for_status()
        result = response.json()
        return result.get('data', {}).get('id')
    
    def add_signers(self, envelope_id: str, signers: List[Dict[str, Any]]) -> None:
        """Adiciona signatários ao envelope"""
        for signer in signers:
            url = f"{self.base_url}/envelopes/{envelope_id}/signers"
            payload = {
                "data": {
                    "type": "signers",
                    "attributes": {
                        "email": signer['email'],
                        "name": signer.get('name', signer['email']),
                        "order": signer.get('order', 1)
                    }
                }
            }
            
            response = requests.post(
                url,
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            response.raise_for_status()
    
    def send_to_sign(self, envelope_id: str, message: Optional[str] = None) -> None:
        """Envia envelope para assinatura"""
        url = f"{self.base_url}/envelopes/{envelope_id}"
        payload = {
            "data": {
                "type": "envelopes",
                "attributes": {
                    "status": "running"
                }
            }
        }
        
        response = requests.patch(
            url,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
    
    def get_status(self, envelope_id: str) -> SignatureStatus:
        """Consulta status do envelope"""
        url = f"{self.base_url}/envelopes/{envelope_id}"
        response = requests.get(
            url,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        data = response.json()
        status = data.get('data', {}).get('attributes', {}).get('status', 'draft')
        
        # Mapear status do ClickSign para enum normalizado
        status_map = {
            'draft': SignatureStatus.DRAFT,
            'running': SignatureStatus.SENT,
            'closed': SignatureStatus.SIGNED,
            'canceled': SignatureStatus.CANCELED
        }
        
        return status_map.get(status, SignatureStatus.ERROR)
    
    def get_signer_status(self, envelope_id: str) -> List[Dict[str, Any]]:
        """Consulta status individual dos signatários"""
        url = f"{self.base_url}/envelopes/{envelope_id}/signers"
        response = requests.get(
            url,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        data = response.json()
        signers_data = data.get('data', [])
        
        result = []
        for signer in signers_data:
            attrs = signer.get('attributes', {})
            result.append({
                'email': attrs.get('email'),
                'name': attrs.get('name'),
                'status': attrs.get('status', 'pending'),
                'signed_at': attrs.get('signed_at')
            })
        
        return result
    
    def download_signed_document(self, envelope_id: str) -> bytes:
        """Baixa documento assinado"""
        url = f"{self.base_url}/envelopes/{envelope_id}/download"
        response = requests.get(
            url,
            headers={"Authorization": self.api_key},
            stream=True
        )
        
        response.raise_for_status()
        return response.content
    
    def cancel(self, envelope_id: str) -> None:
        """Cancela envelope"""
        url = f"{self.base_url}/envelopes/{envelope_id}"
        response = requests.delete(
            url,
            headers={"Authorization": self.api_key}
        )
        
        response.raise_for_status()
    
    def verify_webhook_signature(self, request) -> bool:
        """Verifica assinatura do webhook (ClickSign não usa assinatura por padrão)"""
        # ClickSign não valida assinatura de webhook por padrão
        # Pode implementar validação customizada se necessário
        return True
    
    def parse_webhook_event(self, payload: Dict) -> Dict[str, Any]:
        """Parse evento de webhook do ClickSign"""
        from datetime import datetime
        
        event = payload.get('event', {})
        event_type = event.get('type')
        envelope_id = event.get('data', {}).get('id')
        
        # Mapear tipos de evento
        event_type_map = {
            'envelope.created': 'document.created',
            'envelope.running': 'document.sent',
            'envelope.closed': 'document.signed',
            'envelope.canceled': 'document.canceled',
            'signer.viewed': 'document.viewed',
            'signer.signed': 'document.signed'
        }
        
        normalized_type = event_type_map.get(event_type, event_type)
        
        # Converter timestamp se necessário
        timestamp = event.get('created_at')
        if timestamp and isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        elif not timestamp:
            timestamp = datetime.utcnow()
        
        return {
            'event_type': normalized_type,
            'envelope_id': envelope_id,
            'signer_email': event.get('data', {}).get('attributes', {}).get('email'),
            'timestamp': timestamp,
            'status': self._map_event_to_status(normalized_type)
        }
    
    def _map_event_to_status(self, event_type: str) -> SignatureStatus:
        """Mapeia tipo de evento para status"""
        if 'signed' in event_type:
            return SignatureStatus.SIGNED
        elif 'sent' in event_type:
            return SignatureStatus.SENT
        elif 'viewed' in event_type:
            return SignatureStatus.VIEWED
        elif 'canceled' in event_type:
            return SignatureStatus.CANCELED
        else:
            return SignatureStatus.WAITING_SIGNATURE
    
    def get_provider_name(self) -> str:
        return 'clicksign'
    
    def get_external_url(self, envelope_id: str) -> str:
        return f"https://app.clicksign.com/envelopes/{envelope_id}"
