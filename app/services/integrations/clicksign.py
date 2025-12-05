from typing import Dict, Any, List
from app.models import GeneratedDocument, SignatureRequest, DataSourceConnection
from app.database import db
import requests
import logging
from .base import BaseIntegration

logger = logging.getLogger(__name__)

class ClickSignIntegration(BaseIntegration):
    """
    Integração com ClickSign para assinatura de documentos.
    Usa DataSourceConnection para gerenciar credenciais.
    """
    
    BASE_URL = "https://sandbox.clicksign.com/api/v3"
    
    def __init__(self, organization_id: str):
        super().__init__(organization_id)
        self._load_config()
    
    def _load_config(self):
        """Carrega configuração da conexão ClickSign para a organização"""
        connection = DataSourceConnection.query.filter_by(
            organization_id=self.organization_id,
            source_type='clicksign',
            status='active'
        ).first()
        
        if not connection:
            raise Exception('ClickSign não está configurado para esta organização. Crie uma conexão primeiro.')
        
        # Descriptografar credenciais
        credentials = connection.get_decrypted_credentials()
        
        # Buscar api_key das credenciais descriptografadas
        # Suporta tanto 'api_key' (novo formato) quanto 'clicksign_api_key' (legado)
        self.api_key = credentials.get('api_key') or credentials.get('clicksign_api_key')
        
        if not self.api_key:
            raise Exception('API Key do ClickSign não configurada na conexão')
    
    def send_document_for_signature(
        self,
        document: GeneratedDocument,
        signers: List[Dict],
        message: str = None
    ) -> SignatureRequest:
        """
        Envia documento gerado para assinatura no ClickSign.
        
        Args:
            document: Documento gerado
            signers: Lista de signatários [{"email": "...", "name": "...", "order": 1}]
            message: Mensagem opcional para os signatários
        
        Returns:
            SignatureRequest criado
        """
        try:
            # 1. Criar envelope
            envelope_id = self._create_envelope(document.name or f"Documento {document.id}")
            
            # 2. Adicionar documento ao envelope (via PDF se disponível)
            if document.pdf_file_id:
                # Baixar PDF do Google Drive e fazer upload
                doc_id = self._upload_document_to_clicksign(document.pdf_file_id, document.name or "documento.pdf")
            elif document.google_doc_id:
                # Exportar como PDF e fazer upload
                doc_id = self._upload_google_doc_to_clicksign(document.google_doc_id, document.name or "documento.pdf")
            else:
                raise Exception('Documento não possui PDF ou Google Doc disponível')
            
            # 3. Adicionar signatários
            for signer in signers:
                self._add_signer(envelope_id, signer['email'], signer['name'], signer.get('order', 1))
            
            # 4. Enviar envelope
            self._send_envelope(envelope_id)
            
            # 5. Criar registro SignatureRequest
            signature_request = SignatureRequest(
                organization_id=self.organization_id,
                generated_document_id=document.id,
                provider='clicksign',
                external_id=envelope_id,
                external_url=f"https://app.clicksign.com/envelopes/{envelope_id}",
                status='sent',
                signers=signers,
                sent_at=db.func.now()
            )
            
            db.session.add(signature_request)
            db.session.commit()
            
            return signature_request
            
        except Exception as e:
            logger.error(f"Erro ao enviar documento para assinatura: {str(e)}")
            raise
    
    def _create_envelope(self, name: str) -> str:
        """Cria envelope no ClickSign"""
        url = f"{self.BASE_URL}/envelopes"
        
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
        
        if not response.ok:
            raise Exception(f"Erro ao criar envelope: {response.text}")
        
        data = response.json()
        return data.get('data', {}).get('id')
    
    def _upload_document_to_clicksign(self, file_id: str, filename: str) -> str:
        """Upload de documento para ClickSign (via Google Drive file_id)"""
        # TODO: Implementar download do Google Drive e upload para ClickSign
        # Por enquanto, retornar placeholder
        raise NotImplementedError("Upload de documento ainda não implementado")
    
    def _upload_google_doc_to_clicksign(self, doc_id: str, filename: str) -> str:
        """Exporta Google Doc como PDF e faz upload para ClickSign"""
        # TODO: Implementar exportação e upload
        raise NotImplementedError("Upload de Google Doc ainda não implementado")
    
    def _add_signer(self, envelope_id: str, email: str, name: str, order: int = 1):
        """Adiciona signatário ao envelope"""
        url = f"{self.BASE_URL}/envelopes/{envelope_id}/signers"
        
        payload = {
            "data": {
                "type": "signers",
                "attributes": {
                    "email": email,
                    "name": name,
                    "order": order
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
        
        if not response.ok:
            raise Exception(f"Erro ao adicionar signatário: {response.text}")
    
    def _send_envelope(self, envelope_id: str):
        """Envia envelope para assinatura"""
        url = f"{self.BASE_URL}/envelopes/{envelope_id}"
        
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
        
        if not response.ok:
            raise Exception(f"Erro ao enviar envelope: {response.text}")
    
    def get_signature_status(self, signature_request_id: str) -> Dict:
        """Consulta status de uma solicitação de assinatura"""
        signature_request = SignatureRequest.query.filter_by(
            id=signature_request_id,
            organization_id=self.organization_id
        ).first_or_404()
        
        if not signature_request.external_id:
            return {
                'status': signature_request.status,
                'error': 'External ID não encontrado'
            }
        
        # Consultar status no ClickSign
        url = f"{self.BASE_URL}/envelopes/{signature_request.external_id}"
        
        response = requests.get(
            url,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json"
            }
        )
        
        if not response.ok:
            return {
                'status': signature_request.status,
                'error': f'Erro ao consultar status: {response.text}'
            }
        
        data = response.json()
        envelope_data = data.get('data', {}).get('attributes', {})
        
        # Atualizar status local
        status_map = {
            'draft': 'pending',
            'running': 'sent',
            'closed': 'signed',
            'canceled': 'declined'
        }
        
        clicksign_status = envelope_data.get('status', 'draft')
        new_status = status_map.get(clicksign_status, signature_request.status)
        
        if new_status != signature_request.status:
            signature_request.status = new_status
            if new_status == 'signed':
                signature_request.completed_at = db.func.now()
            db.session.commit()
        
        return {
            'status': signature_request.status,
            'external_status': clicksign_status,
            'signers': signature_request.signers,
            'external_url': signature_request.external_url
        }
    
    def handle_webhook(self, payload: Dict) -> None:
        """Processa webhook do ClickSign"""
        # TODO: Implementar processamento de webhook
        event_type = payload.get('event', {}).get('type')
        envelope_id = payload.get('event', {}).get('data', {}).get('id')
        
        if not envelope_id:
            logger.warning("Webhook sem envelope_id")
            return
        
        # Buscar SignatureRequest pelo external_id
        signature_request = SignatureRequest.query.filter_by(
            external_id=envelope_id,
            provider='clicksign'
        ).first()
        
        if not signature_request:
            logger.warning(f"SignatureRequest não encontrado para envelope {envelope_id}")
            return
        
        # Atualizar status baseado no evento
        if event_type == 'envelope.closed':
            signature_request.status = 'signed'
            signature_request.completed_at = db.func.now()
        elif event_type == 'envelope.canceled':
            signature_request.status = 'declined'
        
        signature_request.webhook_data = payload
        db.session.commit()

