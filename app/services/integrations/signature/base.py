"""
Interface base para adapters de providers de assinatura eletrônica.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from app.models import GeneratedDocument, SignatureRequest
from enum import Enum
import logging

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class SignatureStatus(Enum):
    """Status normalizado de assinatura"""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    WAITING_SIGNATURE = "waiting_signature"
    PARTIAL = "partial"  # Alguns signatários assinaram
    SIGNED = "signed"  # Todos assinaram
    DECLINED = "declined"
    CANCELED = "canceled"
    EXPIRED = "expired"
    ERROR = "error"

class SignatureProviderAdapter(ABC):
    """
    Interface base para adapters de providers de assinatura.
    Todos os providers devem implementar esta interface.
    """
    
    def __init__(self, organization_id: str, connection_id: str):
        self.organization_id = organization_id
        self.connection_id = connection_id
        self._load_connection()
    
    @abstractmethod
    def _load_connection(self):
        """Carrega e valida conexão do banco de dados"""
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Testa conexão com o provider.
        
        Returns:
            {
                'valid': bool,
                'message': str,
                'provider_info': dict (opcional)
            }
        """
        pass
    
    @abstractmethod
    def create_envelope(self, name: str) -> str:
        """
        Cria envelope/documento no provider.
        
        Args:
            name: Nome do envelope/documento
            
        Returns:
            envelope_id: ID do envelope criado
        """
        pass
    
    @abstractmethod
    def upload_document(self, envelope_id: str, file_bytes: bytes, filename: str) -> str:
        """
        Faz upload de documento PDF para o envelope.
        
        Args:
            envelope_id: ID do envelope
            file_bytes: Conteúdo do arquivo PDF
            filename: Nome do arquivo
            
        Returns:
            document_id: ID do documento no provider
        """
        pass
    
    @abstractmethod
    def add_signers(self, envelope_id: str, signers: List[Dict[str, Any]]) -> None:
        """
        Adiciona signatários ao envelope.
        
        Args:
            envelope_id: ID do envelope
            signers: Lista de signatários [
                {
                    'email': str,
                    'name': str (opcional),
                    'order': int (opcional)
                }
            ]
        """
        pass
    
    @abstractmethod
    def send_to_sign(self, envelope_id: str, message: Optional[str] = None) -> None:
        """
        Envia envelope para assinatura.
        
        Args:
            envelope_id: ID do envelope
            message: Mensagem opcional para os signatários
        """
        pass
    
    @abstractmethod
    def get_status(self, envelope_id: str) -> SignatureStatus:
        """
        Consulta status do envelope.
        
        Args:
            envelope_id: ID do envelope
            
        Returns:
            SignatureStatus: Status normalizado
        """
        pass
    
    @abstractmethod
    def get_signer_status(self, envelope_id: str) -> List[Dict[str, Any]]:
        """
        Consulta status individual de cada signatário.
        
        Args:
            envelope_id: ID do envelope
            
        Returns:
            [
                {
                    'email': str,
                    'name': str,
                    'status': str,  # 'pending', 'viewed', 'signed', 'declined'
                    'signed_at': datetime (opcional)
                }
            ]
        """
        pass
    
    @abstractmethod
    def download_signed_document(self, envelope_id: str) -> bytes:
        """
        Baixa documento assinado.
        
        Args:
            envelope_id: ID do envelope
            
        Returns:
            file_bytes: Conteúdo do PDF assinado
        """
        pass
    
    @abstractmethod
    def cancel(self, envelope_id: str) -> None:
        """
        Cancela envelope.
        
        Args:
            envelope_id: ID do envelope
        """
        pass
    
    @abstractmethod
    def verify_webhook_signature(self, request) -> bool:
        """
        Verifica assinatura do webhook (segurança).
        
        Args:
            request: Objeto request do Flask
            
        Returns:
            bool: True se assinatura é válida
        """
        pass
    
    @abstractmethod
    def parse_webhook_event(self, payload: Dict) -> Dict[str, Any]:
        """
        Parse e normaliza evento de webhook.
        
        Args:
            payload: Payload do webhook
            
        Returns:
            {
                'event_type': str,  # 'document.sent', 'document.signed', etc.
                'envelope_id': str,
                'signer_email': str (opcional),
                'timestamp': datetime,
                'status': SignatureStatus
            }
        """
        pass
    
    def send_document_for_signature(
        self,
        document: GeneratedDocument,
        signers: List[Dict[str, Any]],
        message: Optional[str] = None
    ) -> SignatureRequest:
        """
        Método de alto nível que executa fluxo completo:
        1. Cria envelope
        2. Upload documento
        3. Adiciona signatários
        4. Envia para assinatura
        5. Cria SignatureRequest no banco
        
        Args:
            document: Documento gerado
            signers: Lista de signatários
            message: Mensagem opcional
            
        Returns:
            SignatureRequest criado
        """
        from app.database import db
        
        # 1. Criar envelope
        envelope_name = document.name or f"Documento {document.id}"
        envelope_id = self.create_envelope(envelope_name)
        
        # 2. Upload documento
        # Baixar PDF do Google Drive ou OneDrive
        file_bytes, storage_type = self._get_pdf_bytes(document)
        if not file_bytes:
            raise ValueError("Documento não possui PDF disponível")
        
        filename = f"{document.name or 'documento'}.pdf"
        if not filename.endswith('.pdf'):
            filename = f"{filename}.pdf"
        
        self.upload_document(envelope_id, file_bytes, filename)
        
        # 3. Adicionar signatários
        self.add_signers(envelope_id, signers)
        
        # 4. Enviar para assinatura
        self.send_to_sign(envelope_id, message)
        
        # 5. Criar SignatureRequest
        signature_request = SignatureRequest(
            organization_id=self.organization_id,
            generated_document_id=document.id,
            provider=self.get_provider_name(),
            external_id=envelope_id,
            external_url=self.get_external_url(envelope_id),
            status='sent',
            signers=signers,
            sent_at=db.func.now()
        )
        
        db.session.add(signature_request)
        db.session.commit()
        
        return signature_request
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Retorna nome do provider ('clicksign', 'zapsign')"""
        pass
    
    @abstractmethod
    def get_external_url(self, envelope_id: str) -> str:
        """Retorna URL externa do envelope no provider"""
        pass
    
    def _get_pdf_bytes(self, document: GeneratedDocument) -> Tuple[bytes, str]:
        """
        Obtém bytes do PDF do documento, tentando diferentes fontes.
        
        Args:
            document: Documento gerado
            
        Returns:
            Tuple[bytes, str]: (conteúdo do PDF, tipo de storage)
            
        Raises:
            ValueError: Se não conseguir obter PDF
        """
        from app.services.integrations.signature.document_downloader import DocumentDownloader
        
        downloader = DocumentDownloader(self.organization_id)
        
        # Prioridade 1: pdf_file_id (PDF já gerado)
        if document.pdf_file_id:
            # Determinar storage type baseado no workflow ou conexão
            storage_type = self._determine_storage_type(document)
            try:
                file_bytes = downloader.download_pdf(document.pdf_file_id, storage_type)
                return file_bytes, storage_type
            except Exception as e:
                logger.warning(f"Erro ao baixar PDF por pdf_file_id: {str(e)}")
        
        # Prioridade 2: google_doc_id (exportar como PDF)
        if document.google_doc_id:
            try:
                # Verificar se é Google Docs ou Microsoft
                try:
                    file_info = downloader.get_file_info(document.google_doc_id, 'google_drive')
                    mime_type = file_info.get('mime_type', '')
                    
                    if 'google-apps' in mime_type:
                        # É Google Doc/Slides, exportar como PDF
                        file_bytes = downloader.download_pdf(document.google_doc_id, 'google_drive')
                        return file_bytes, 'google_drive'
                except:
                    # Pode ser Microsoft (armazenado no campo google_doc_id)
                    # Tentar baixar do OneDrive
                    try:
                        file_bytes = downloader.download_pdf(document.google_doc_id, 'microsoft')
                        return file_bytes, 'microsoft'
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Erro ao exportar documento: {str(e)}")
        
        raise ValueError("Não foi possível obter PDF do documento")
    
    def _determine_storage_type(self, document: GeneratedDocument) -> str:
        """
        Determina o tipo de storage baseado no documento e workflow.
        
        Args:
            document: Documento gerado
            
        Returns:
            str: 'google_drive' ou 'microsoft'
        """
        # Verificar se tem google_doc_id mas não é Google Apps
        # Se sim, provavelmente é Microsoft (reutilizando campo)
        if document.google_doc_id and not document.pdf_file_id:
            # Tentar inferir do workflow ou template
            if document.workflow:
                # Verificar nodes do workflow para determinar storage
                # Model removed during JSONB migration
                nodes = WorkflowNode.query.filter_by(
                    workflow_id=document.workflow_id
                ).all()
                
                for node in nodes:
                    if node.node_type in ['microsoft-word', 'microsoft-powerpoint']:
                        return 'microsoft'
                    elif node.node_type in ['google-docs', 'google-slides']:
                        return 'google_drive'
        
        # Default: Google Drive
        return 'google_drive'
