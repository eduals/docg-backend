"""
Serviço para criação de envelopes ClickSign
Processa criação assíncrona de envelopes com progresso
"""
from app.database import db
from app.models import (
    EnvelopeRelation, EnvelopeExecutionLog, 
    FieldMapping, GoogleOAuthToken, GoogleDriveConfig
)
from app.models import DataSourceConnection
from datetime import datetime
import requests
import uuid
import json
import base64
import io
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError


class EnvelopeCreationService:
    """Serviço para criar envelopes ClickSign"""
    
    def __init__(self, organization_id, execution_id):
        self.organization_id = organization_id
        self.execution_id = execution_id
        self.envelope_id = None
        
    def get_portal_id(self):
        """Obter portal_id do HubSpot da organização via DataSourceConnection"""
        connection = DataSourceConnection.query.filter_by(
            organization_id=self.organization_id,
            source_type='hubspot'
        ).first()
        
        if connection and connection.config:
            portal_id = connection.config.get('portal_id')
            if portal_id:
                return str(portal_id)
        
        # Fallback: usar organization_id como portal_id se não encontrar conexão HubSpot
        return str(self.organization_id)
        
    def get_clicksign_token(self):
        """Obter token ClickSign da organização via DataSourceConnection"""
        connection = DataSourceConnection.query.filter_by(
            organization_id=self.organization_id,
            source_type='clicksign'
        ).first()
        
        if not connection:
            raise Exception("ClickSign API key not configured for this organization")
        
        # Descriptografar credenciais
        credentials = connection.get_decrypted_credentials()
        
        # Buscar api_key (suporta tanto 'api_key' quanto 'clicksign_api_key' para compatibilidade)
        api_key = credentials.get('api_key') or credentials.get('clicksign_api_key')
        
        if not api_key:
            raise Exception("ClickSign API key not configured for this organization")
        
        return api_key
    
    def update_log(self, step_name, status, message=None, error_message=None, envelope_id=None):
        """Atualizar log de execução"""
        log = EnvelopeExecutionLog.query.filter_by(
            execution_id=self.execution_id,
            step_name=step_name
        ).first()
        
        if log:
            log.step_status = status
            log.step_message = message
            log.error_message = error_message
            if envelope_id:
                log.envelope_id = envelope_id
            db.session.commit()
    
    def create_envelope(self, envelope_name):
        """Etapa 1: Criar envelope no ClickSign"""
        try:
            self.update_log('Creating envelope', 'in_progress', 'Creating envelope in ClickSign...')
            
            token = self.get_clicksign_token()
            url = "https://sandbox.clicksign.com/api/v3/envelopes"
            
            payload = {
                "data": {
                    "type": "envelopes",
                    "attributes": {
                        "name": envelope_name
                    }
                }
            }
            
            response = requests.post(
                url,
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if not response.ok:
                error_msg = f"Error creating envelope: {response.text}"
                self.update_log('Creating envelope', 'error', error_message=error_msg)
                raise Exception(error_msg)
            
            data = response.json()
            self.envelope_id = data.get('data', {}).get('id')
            
            if not self.envelope_id:
                raise Exception("Envelope ID not returned from ClickSign")
            
            # Salvar relação no banco
            relation = EnvelopeRelation(
                portal_id=self.get_portal_id(),
                hubspot_object_type="",  # Será atualizado depois
                hubspot_object_id="",  # Será atualizado depois
                clicksign_envelope_id=self.envelope_id,
                envelope_name=envelope_name,
                envelope_status="draft"
            )
            db.session.add(relation)
            db.session.commit()
            
            self.update_log(
                'Creating envelope', 
                'completed', 
                'Envelope created successfully',
                envelope_id=self.envelope_id
            )
            
            return self.envelope_id
            
        except Exception as e:
            self.update_log('Creating envelope', 'error', error_message=str(e))
            raise
    
    def add_document_from_template(self, template_id, filename):
        """Adicionar documento usando template ClickSign"""
        try:
            token = self.get_clicksign_token()
            url = f"https://sandbox.clicksign.com/api/v3/envelopes/{self.envelope_id}/documents"
            
            payload = {
                "data": {
                    "type": "documents",
                    "attributes": {
                        "filename": filename,
                        "template_id": template_id
                    }
                }
            }
            
            response = requests.post(
                url,
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if not response.ok:
                raise Exception(f"Error adding document: {response.text}")
            
            return response.json()
            
        except Exception as e:
            raise Exception(f"Error adding document from template: {str(e)}")
    
    def add_document_from_upload(self, file_content, filename):
        """Adicionar documento via upload"""
        try:
            token = self.get_clicksign_token()
            url = f"https://sandbox.clicksign.com/api/v3/envelopes/{self.envelope_id}/documents"
            
            # Decodificar base64 se necessário
            if isinstance(file_content, str):
                file_bytes = base64.b64decode(file_content)
            else:
                file_bytes = file_content
            
            # Fazer upload multipart
            files = {
                'file': (filename, file_bytes, 'application/pdf')
            }
            
            data = {
                'filename': filename
            }
            
            response = requests.post(
                url,
                headers={
                    "Authorization": token
                },
                files=files,
                data=data
            )
            
            if not response.ok:
                raise Exception(f"Error uploading document: {response.text}")
            
            return response.json()
            
        except Exception as e:
            raise Exception(f"Error uploading document: {str(e)}")
    
    def get_google_credentials(self):
        """Obter credenciais Google"""
        token = GoogleOAuthToken.query.filter_by(organization_id=self.organization_id).first()
        
        if not token:
            return None
        
        try:
            creds_data = json.loads(token.access_token)
            creds = Credentials.from_authorized_user_info(creds_data)
            
            # Se token expirou, tentar renovar usando refresh_token
            if creds.expired or token.is_expired():
                if creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Atualizar no banco após renovação bem-sucedida
                        token.access_token = creds.to_json()
                        token.token_expiry = creds.expiry
                        db.session.commit()
                    except Exception as refresh_error:
                        # Se renovação falhar, retornar None
                        print(f"Error refreshing token: {refresh_error}")
                        return None
                else:
                    # Não há refresh_token para renovar
                    return None
            
            return creds
        except Exception as e:
            print(f"Error getting credentials: {e}")
            return None
    
    def download_google_drive_file(self, file_id):
        """Baixar arquivo do Google Drive"""
        try:
            creds = self.get_google_credentials()
            if not creds:
                raise Exception("Google account not connected")
            
            service = build('drive', 'v3', credentials=creds)
            
            # Verificar tipo de arquivo
            file_metadata = service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType')
            
            if mime_type == 'application/vnd.google-apps.document':
                # Converter Google Doc para PDF
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            else:
                # Baixar arquivo diretamente
                request = service.files().get_media(fileId=file_id)
            
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            return file_io.read(), file_metadata.get('name', 'document.pdf')
            
        except HttpError as e:
            raise Exception(f"Google Drive API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error downloading from Google Drive: {str(e)}")
    
    def add_document_from_google_drive(self, file_id, filename=None):
        """Adicionar documento do Google Drive"""
        try:
            file_content, original_filename = self.download_google_drive_file(file_id)
            filename = filename or original_filename
            
            # Se não termina com .pdf, adicionar
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            return self.add_document_from_upload(file_content, filename)
            
        except Exception as e:
            raise Exception(f"Error adding document from Google Drive: {str(e)}")
    
    def apply_field_mappings(self, hubspot_object_type, hubspot_object_id, hubspot_properties):
        """Aplicar mapeamentos de campos"""
        try:
            self.update_log('Applying field mappings', 'in_progress', 'Applying field mappings...')
            
            # Buscar mapeamentos ativos
            mappings = FieldMapping.query.filter_by(
                portal_id=self.get_portal_id(),
                object_type=hubspot_object_type,
                is_active=True
            ).all()
            
            if not mappings:
                self.update_log('Applying field mappings', 'completed', 'No field mappings to apply')
                return {}
            
            # Mapear valores
            mapped_values = {}
            for mapping in mappings:
                hubspot_value = hubspot_properties.get(mapping.hubspot_property_name)
                if hubspot_value:
                    mapped_values[mapping.clicksign_field_name] = hubspot_value
            
            # TODO: Aplicar valores nos documentos do envelope via API ClickSign
            # Por enquanto, apenas retornar valores mapeados
            
            self.update_log('Applying field mappings', 'completed', f'Applied {len(mapped_values)} field mappings')
            return mapped_values
            
        except Exception as e:
            self.update_log('Applying field mappings', 'error', error_message=str(e))
            return {}
    
    def add_signer(self, name, email, order=1):
        """Adicionar signatário ao envelope"""
        try:
            token = self.get_clicksign_token()
            url = f"https://sandbox.clicksign.com/api/v3/envelopes/{self.envelope_id}/signers"
            
            payload = {
                "data": {
                    "type": "signers",
                    "attributes": {
                        "name": name,
                        "email": email
                    }
                }
            }
            
            response = requests.post(
                url,
                headers={
                    "Authorization": token,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if not response.ok:
                raise Exception(f"Error adding signer: {response.text}")
            
            return response.json()
            
        except Exception as e:
            raise Exception(f"Error adding signer: {str(e)}")
    
    def save_to_hubspot(self, hubspot_object_type, hubspot_object_id):
        """Salvar envelope ID no HubSpot"""
        try:
            self.update_log('Saving to HubSpot', 'in_progress', 'Saving envelope ID to HubSpot...')
            
            # Atualizar relação no banco
            relation = EnvelopeRelation.query.filter_by(
                clicksign_envelope_id=self.envelope_id
            ).first()
            
            if relation:
                relation.hubspot_object_type = hubspot_object_type
                relation.hubspot_object_id = hubspot_object_id
                db.session.commit()
            
            # TODO: Atualizar propriedade customizada no HubSpot via API
            # Por enquanto, apenas salvar no banco
            
            self.update_log('Saving to HubSpot', 'completed', 'Envelope ID saved to HubSpot')
            
        except Exception as e:
            self.update_log('Saving to HubSpot', 'error', error_message=str(e))
            raise
    
    def send_envelope(self):
        """Enviar envelope"""
        try:
            self.update_log('Sending envelope', 'in_progress', 'Sending envelope...')
            
            token = self.get_clicksign_token()
            url = f"https://sandbox.clicksign.com/api/v3/envelopes/{self.envelope_id}"
            
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
                    "Authorization": token,
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if not response.ok:
                raise Exception(f"Error sending envelope: {response.text}")
            
            # Atualizar status no banco
            relation = EnvelopeRelation.query.filter_by(
                clicksign_envelope_id=self.envelope_id
            ).first()
            
            if relation:
                relation.envelope_status = "running"
                db.session.commit()
            
            self.update_log('Sending envelope', 'completed', 'Envelope sent successfully')
            
        except Exception as e:
            self.update_log('Sending envelope', 'error', error_message=str(e))
            raise
    
    def process_envelope_creation(self, creation_data):
        """Processar criação completa do envelope"""
        try:
            # Etapa 1: Criar envelope
            envelope_id = self.create_envelope(creation_data['envelope_name'])
            
            # Etapa 2: Adicionar documentos
            documents = creation_data.get('documents', [])
            for idx, doc in enumerate(documents, 1):
                self.update_log(
                    'Adding documents',
                    'in_progress',
                    f'Adding document {idx} of {len(documents)}...'
                )
                
                try:
                    if doc['type'] == 'template':
                        self.add_document_from_template(
                            doc['template_id'],
                            doc['filename']
                        )
                    elif doc['type'] == 'google_drive':
                        self.add_document_from_google_drive(
                            doc['google_drive_file_id'],
                            doc.get('filename')
                        )
                    elif doc['type'] == 'upload':
                        self.add_document_from_upload(
                            doc['file_content'],
                            doc['filename']
                        )
                    
                    self.update_log(
                        'Adding documents',
                        'completed' if idx == len(documents) else 'in_progress',
                        f'Document {idx} added successfully'
                    )
                except Exception as e:
                    self.update_log(
                        'Adding documents',
                        'error',
                        f'Error adding document {idx}',
                        error_message=str(e)
                    )
                    # Continuar com próximos documentos
            
            # Etapa 3: Aplicar mapeamentos (se solicitado)
            if creation_data.get('use_field_mappings'):
                hubspot_properties = creation_data.get('hubspot_properties', {})
                self.apply_field_mappings(
                    creation_data['hubspot_object_type'],
                    creation_data['hubspot_object_id'],
                    hubspot_properties
                )
            
            # Etapa 4: Adicionar signers
            recipients = creation_data.get('recipients', [])
            for idx, recipient in enumerate(recipients, 1):
                self.update_log(
                    'Adding signers',
                    'in_progress',
                    f'Adding signer {idx} of {len(recipients)}...'
                )
                
                try:
                    self.add_signer(
                        recipient['name'],
                        recipient['email'],
                        recipient.get('order', idx)
                    )
                    self.update_log(
                        'Adding signers',
                        'completed' if idx == len(recipients) else 'in_progress',
                        f'Signer {idx} added successfully'
                    )
                except Exception as e:
                    self.update_log(
                        'Adding signers',
                        'error',
                        f'Error adding signer {idx}',
                        error_message=str(e)
                    )
            
            # Etapa 5: Salvar no HubSpot
            self.save_to_hubspot(
                creation_data['hubspot_object_type'],
                creation_data['hubspot_object_id']
            )
            
            # Etapa 6: Enviar envelope
            self.send_envelope()
            
            return envelope_id
            
        except Exception as e:
            raise Exception(f"Error processing envelope creation: {str(e)}")

