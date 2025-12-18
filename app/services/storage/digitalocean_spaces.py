"""
Serviço de Storage DigitalOcean Spaces - Upload e gerenciamento de arquivos.
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import os
import logging
from typing import Optional
from flask import current_app

logger = logging.getLogger(__name__)


class DigitalOceanSpacesService:
    """
    Serviço para gerenciar arquivos no DigitalOcean Spaces.
    
    Compatível com API S3, usando boto3.
    """
    
    def __init__(self):
        """Inicializa cliente do DigitalOcean Spaces"""
        config = current_app.config if current_app else None
        
        if config:
            self.endpoint = config.get('DO_SPACES_ENDPOINT', 'https://nyc3.digitaloceanspaces.com')
            self.bucket = config.get('DO_SPACES_BUCKET', 'pipehub')
            self.access_key = config.get('DO_SPACES_ACCESS_KEY', '')
            self.secret_key = config.get('DO_SPACES_SECRET_KEY', '')
        else:
            # Fallback para variáveis de ambiente diretas
            self.endpoint = os.getenv('DO_SPACES_ENDPOINT', 'https://nyc3.digitaloceanspaces.com')
            self.bucket = os.getenv('DO_SPACES_BUCKET', 'pipehub')
            self.access_key = os.getenv('DO_SPACES_ACCESS_KEY', '')
            self.secret_key = os.getenv('DO_SPACES_SECRET_KEY', '')
        
        if not self.access_key or not self.secret_key:
            logger.warning("DigitalOcean Spaces credentials not configured")
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4')
        )
    
    def upload_file(self, file_obj, key: str, content_type: str) -> str:
        """
        Upload arquivo para DigitalOcean Spaces.
        
        Args:
            file_obj: File object ou file-like object
            key: Chave do arquivo no Spaces (ex: 'docg/{org_id}/templates/{filename}')
            content_type: MIME type do arquivo
        
        Returns:
            URL pública do arquivo
        
        Raises:
            ClientError: Se houver erro no upload
        """
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs={
                    'ContentType': content_type,
                    'ACL': 'private'  # Arquivos privados por padrão
                }
            )
            
            # Retornar URL pública
            url = f"https://{self.bucket}.nyc3.digitaloceanspaces.com/{key}"
            logger.info(f"File uploaded to Spaces: {key}")
            return url
            
        except ClientError as e:
            logger.error(f"Error uploading file to Spaces: {str(e)}")
            raise Exception(f"Erro ao fazer upload do arquivo: {str(e)}")
    
    def generate_signed_url(self, key: str, expiration: int = 3600) -> str:
        """
        Gera URL assinada temporária para download/visualização.
        
        Args:
            key: Chave do arquivo no Spaces
            expiration: Tempo de expiração em segundos (default: 1 hora)
        
        Returns:
            URL assinada temporária
        
        Raises:
            ClientError: Se houver erro ao gerar URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"Generated signed URL for {key} (expires in {expiration}s)")
            return url
            
        except ClientError as e:
            logger.error(f"Error generating signed URL: {str(e)}")
            raise Exception(f"Erro ao gerar URL assinada: {str(e)}")
    
    def delete_file(self, key: str):
        """
        Deleta arquivo do DigitalOcean Spaces.
        
        Args:
            key: Chave do arquivo no Spaces
        
        Raises:
            ClientError: Se houver erro ao deletar
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"File deleted from Spaces: {key}")
            
        except ClientError as e:
            logger.error(f"Error deleting file from Spaces: {str(e)}")
            raise Exception(f"Erro ao deletar arquivo: {str(e)}")
    
    def file_exists(self, key: str) -> bool:
        """
        Verifica se arquivo existe no Spaces.
        
        Args:
            key: Chave do arquivo no Spaces
        
        Returns:
            True se arquivo existe, False caso contrário
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
