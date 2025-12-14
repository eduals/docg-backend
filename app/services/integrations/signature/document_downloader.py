"""
Serviço helper para download de documentos PDF do Google Drive ou OneDrive.
"""
import io
import logging
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
import requests
import json

logger = logging.getLogger(__name__)

class DocumentDownloader:
    """Serviço para download de documentos PDF de diferentes storages"""
    
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
    
    def download_pdf(self, file_id: str, storage_type: str = 'google_drive') -> bytes:
        """
        Baixa PDF do storage especificado.
        
        Args:
            file_id: ID do arquivo
            storage_type: 'google_drive' ou 'microsoft'
            
        Returns:
            bytes: Conteúdo do PDF
        """
        if storage_type == 'google_drive':
            return self._download_from_google_drive(file_id)
        elif storage_type == 'microsoft':
            return self._download_from_onedrive(file_id)
        else:
            raise ValueError(f"Storage type não suportado: {storage_type}")
    
    def _download_from_google_drive(self, file_id: str) -> bytes:
        """Baixa PDF do Google Drive"""
        try:
            creds = self._get_google_credentials()
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
            elif mime_type == 'application/vnd.google-apps.presentation':
                # Converter Google Slides para PDF
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            elif mime_type == 'application/pdf':
                # Baixar PDF diretamente
                request = service.files().get_media(fileId=file_id)
            else:
                raise Exception(f"Tipo de arquivo não suportado: {mime_type}")
            
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_io.seek(0)
            return file_io.read()
            
        except HttpError as e:
            logger.error(f"Google Drive API error: {str(e)}")
            raise Exception(f"Erro ao baixar do Google Drive: {str(e)}")
        except Exception as e:
            logger.error(f"Error downloading from Google Drive: {str(e)}")
            raise
    
    def _download_from_onedrive(self, file_id: str) -> bytes:
        """Baixa PDF do OneDrive/Microsoft"""
        try:
            access_token = self._get_microsoft_access_token()
            if not access_token:
                raise Exception("Microsoft account not connected")
            
            # Baixar arquivo do OneDrive
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
            response = requests.get(
                url,
                headers={'Authorization': f'Bearer {access_token}'},
                stream=True
            )
            
            if not response.ok:
                raise Exception(f"Erro ao baixar do OneDrive: {response.status_code}")
            
            return response.content
            
        except Exception as e:
            logger.error(f"Error downloading from OneDrive: {str(e)}")
            raise
    
    def _get_google_credentials(self) -> Optional[Credentials]:
        """Obtém credenciais do Google"""
        from app.models import GoogleOAuthToken
        from app.database import db
        
        token = GoogleOAuthToken.query.filter_by(
            organization_id=self.organization_id
        ).first()
        
        if not token:
            return None
        
        try:
            creds_data = json.loads(token.access_token)
            creds = Credentials.from_authorized_user_info(creds_data)
            
            # Renovar token se expirado
            if creds.expired or token.is_expired():
                if creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        token.access_token = creds.to_json()
                        token.token_expiry = creds.expiry
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Error refreshing Google token: {e}")
                        return None
            
            return creds
        except Exception as e:
            logger.error(f"Error getting Google credentials: {e}")
            return None
    
    def _get_microsoft_access_token(self) -> Optional[str]:
        """Obtém access token do Microsoft"""
        from app.models import DataSourceConnection
        
        connection = DataSourceConnection.query.filter_by(
            organization_id=self.organization_id,
            source_type='microsoft',
            status='active'
        ).first()
        
        if not connection:
            return None
        
        credentials = connection.get_decrypted_credentials()
        return credentials.get('access_token')
    
    def get_file_info(self, file_id: str, storage_type: str = 'google_drive') -> dict:
        """
        Obtém informações do arquivo (nome, tamanho, etc).
        
        Args:
            file_id: ID do arquivo
            storage_type: 'google_drive' ou 'microsoft'
            
        Returns:
            dict: Informações do arquivo
        """
        if storage_type == 'google_drive':
            return self._get_google_drive_file_info(file_id)
        elif storage_type == 'microsoft':
            return self._get_onedrive_file_info(file_id)
        else:
            raise ValueError(f"Storage type não suportado: {storage_type}")
    
    def _get_google_drive_file_info(self, file_id: str) -> dict:
        """Obtém informações do arquivo no Google Drive"""
        creds = self._get_google_credentials()
        if not creds:
            raise Exception("Google account not connected")
        
        service = build('drive', 'v3', credentials=creds)
        file_metadata = service.files().get(fileId=file_id).execute()
        
        return {
            'name': file_metadata.get('name'),
            'mime_type': file_metadata.get('mimeType'),
            'size': file_metadata.get('size'),
            'created_time': file_metadata.get('createdTime')
        }
    
    def _get_onedrive_file_info(self, file_id: str) -> dict:
        """Obtém informações do arquivo no OneDrive"""
        access_token = self._get_microsoft_access_token()
        if not access_token:
            raise Exception("Microsoft account not connected")
        
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}"
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        if not response.ok:
            raise Exception(f"Erro ao obter info do OneDrive: {response.status_code}")
        
        data = response.json()
        return {
            'name': data.get('name'),
            'mime_type': data.get('file', {}).get('mimeType'),
            'size': data.get('size'),
            'created_date_time': data.get('createdDateTime')
        }
