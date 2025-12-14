"""
Adapter para integração com ZapSign.
"""
from typing import Dict, Any, List, Optional
from app.services.integrations.signature.base import SignatureProviderAdapter, SignatureStatus
from app.models import DataSourceConnection, GeneratedDocument, SignatureRequest
import requests
import base64
import logging
from app.database import db

logger = logging.getLogger(__name__)

class ZapSignAdapter(SignatureProviderAdapter):
    """Adapter para ZapSign"""
    
    def __init__(self, organization_id: str, connection_id: str):
        self.api_token = None
        self.base_url = "https://api.zapsign.com.br/api/v1"
        super().__init__(organization_id, connection_id)
    
    def _load_connection(self):
        """Carrega conexão ZapSign"""
        connection = DataSourceConnection.query.filter_by(
            id=self.connection_id,
            organization_id=self.organization_id,
            source_type='zapsign',
            status='active'
        ).first_or_404()
        
        credentials = connection.get_decrypted_credentials()
        self.api_token = credentials.get('api_token') or credentials.get('api_key')
        
        if not self.api_token:
            raise ValueError("API Token do ZapSign não configurado")
    
    def test_connection(self) -> Dict[str, Any]:
        """Testa conexão com ZapSign"""
        try:
            response = requests.get(
                f"{self.base_url}/docs/",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                },
                params={"page": 1, "limit": 1},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'valid': True,
                    'message': 'Conexão válida'
                }
            elif response.status_code == 401:
                return {
                    'valid': False,
                    'message': 'API token inválido ou expirado'
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
        """Cria documento no ZapSign (retorna doc_id)"""
        # ZapSign cria documento e já pode incluir signers
        # Por enquanto, só cria o documento vazio
        url = f"{self.base_url}/docs/"
        payload = {
            "name": name
        }
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
        data = response.json()
        return data.get('id') or data.get('doc_id')
    
    def upload_document(self, envelope_id: str, file_bytes: bytes, filename: str) -> str:
        """Upload de documento para ZapSign"""
        # ZapSign permite upload via base64 ou multipart
        # Usar base64 para simplicidade
        url = f"{self.base_url}/docs/{envelope_id}/upload"
        
        file_base64 = base64.b64encode(file_bytes).decode('utf-8')
        
        payload = {
            "file": file_base64,
            "filename": filename
        }
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
        return envelope_id  # ZapSign usa o mesmo ID
    
    def add_signers(self, envelope_id: str, signers: List[Dict[str, Any]]) -> None:
        """Adiciona signatários ao documento"""
        url = f"{self.base_url}/docs/{envelope_id}/participants"
        
        participants = []
        for idx, signer in enumerate(signers, 1):
            participants.append({
                "email": signer['email'],
                "name": signer.get('name', signer['email']),
                "action": "SIGN",
                "sequence": signer.get('order', idx)
            })
        
        payload = {
            "participants": participants
        }
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
    
    def send_to_sign(self, envelope_id: str, message: Optional[str] = None) -> None:
        """Envia documento para assinatura"""
        # ZapSign envia automaticamente se participantes foram adicionados
        # Mas podemos forçar envio explícito
        url = f"{self.base_url}/docs/{envelope_id}/send"
        
        payload = {}
        if message:
            payload["message"] = message
        
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        response.raise_for_status()
    
    def get_status(self, envelope_id: str) -> SignatureStatus:
        """Consulta status do documento"""
        url = f"{self.base_url}/docs/{envelope_id}"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        data = response.json()
        status = data.get('status', 'draft')
        
        # Mapear status do ZapSign
        status_map = {
            'draft': SignatureStatus.DRAFT,
            'sent': SignatureStatus.SENT,
            'viewed': SignatureStatus.VIEWED,
            'signed': SignatureStatus.SIGNED,
            'canceled': SignatureStatus.CANCELED,
            'expired': SignatureStatus.EXPIRED
        }
        
        return status_map.get(status, SignatureStatus.ERROR)
    
    def get_signer_status(self, envelope_id: str) -> List[Dict[str, Any]]:
        """Consulta status individual dos signatários"""
        url = f"{self.base_url}/docs/{envelope_id}/participants"
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
        data = response.json()
        participants = data.get('participants', [])
        
        result = []
        for participant in participants:
            result.append({
                'email': participant.get('email'),
                'name': participant.get('name'),
                'status': participant.get('status', 'pending'),
                'signed_at': participant.get('signed_at')
            })
        
        return result
    
    def download_signed_document(self, envelope_id: str) -> bytes:
        """Baixa documento assinado"""
        url = f"{self.base_url}/docs/{envelope_id}/download"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.api_token}"},
            stream=True
        )
        
        response.raise_for_status()
        return response.content
    
    def cancel(self, envelope_id: str) -> None:
        """Cancela documento"""
        url = f"{self.base_url}/docs/{envelope_id}/cancel"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
        )
        
        response.raise_for_status()
    
    def verify_webhook_signature(self, request) -> bool:
        """Verifica assinatura do webhook"""
        # ZapSign pode usar header X-ZapSign-Signature
        # Implementar validação se necessário
        return True
    
    def parse_webhook_event(self, payload: Dict) -> Dict[str, Any]:
        """Parse evento de webhook do ZapSign"""
        from datetime import datetime
        
        event_type = payload.get('event')
        doc_id = payload.get('doc_id')
        
        # Mapear tipos de evento
        event_type_map = {
            'doc.created': 'document.created',
            'doc.sent': 'document.sent',
            'doc.viewed': 'document.viewed',
            'doc.signed': 'document.signed',
            'doc.canceled': 'document.canceled',
            'doc.expired': 'document.expired'
        }
        
        normalized_type = event_type_map.get(event_type, event_type)
        
        # Converter timestamp se necessário
        timestamp = payload.get('timestamp')
        if timestamp and isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.utcnow()
        elif not timestamp:
            timestamp = datetime.utcnow()
        
        return {
            'event_type': normalized_type,
            'envelope_id': doc_id,
            'signer_email': payload.get('participant', {}).get('email'),
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
        elif 'expired' in event_type:
            return SignatureStatus.EXPIRED
        else:
            return SignatureStatus.WAITING_SIGNATURE
    
    def get_provider_name(self) -> str:
        return 'zapsign'
    
    def get_external_url(self, envelope_id: str) -> str:
        return f"https://app.zapsign.com.br/docs/{envelope_id}"
