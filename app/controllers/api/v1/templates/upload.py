"""
Upload Template Controller.
"""

from flask import request, jsonify, g
from werkzeug.utils import secure_filename
from app.database import db
from app.models import Template
from app.services.storage import DigitalOceanSpacesService
from .helpers import template_to_dict
import logging
import uuid
import os

logger = logging.getLogger(__name__)


def upload_template():
    """
    Upload de arquivo .doc ou .docx para usar como template.

    Request:
    - Content-Type: multipart/form-data
    - file: Arquivo .doc ou .docx (obrigatório)
    - name: Nome do template (opcional, usa nome do arquivo se não fornecido)
    - description: Descrição (opcional)
    """
    # Validar que arquivo foi enviado
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nome do arquivo vazio'}), 400

    # Validar tipo de arquivo
    allowed_extensions = {'.doc', '.docx'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        return jsonify({
            'error': 'Tipo de arquivo não permitido. Use .doc ou .docx'
        }), 400

    # Validar tamanho (max 10MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Resetar posição

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': 'Arquivo muito grande. Tamanho máximo: 10MB'
        }), 400

    if file_size == 0:
        return jsonify({'error': 'Arquivo vazio'}), 400

    try:
        organization_id = g.organization_id

        # Obter nome e descrição
        template_name = request.form.get('name') or os.path.splitext(file.filename)[0]
        description = request.form.get('description')

        # Determinar MIME type
        mime_types = {
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        content_type = mime_types.get(file_ext, 'application/octet-stream')

        # Gerar nome único para o arquivo
        file_uuid = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        filename = f"{file_uuid}{file_ext}"

        # Key no DigitalOcean Spaces
        storage_key = f"docg/{organization_id}/templates/{filename}"

        # Upload para DigitalOcean Spaces
        storage_service = DigitalOceanSpacesService()
        storage_url = storage_service.upload_file(file, storage_key, content_type)

        # Extrair tags do documento (opcional)
        detected_tags = []
        try:
            from app.services.document_generation.document_converter import DocumentConverter
            from docx import Document
            from app.services.document_generation.tag_processor import TagProcessor
            import io

            file.seek(0)
            file_bytes = file.read()

            # Normalizar documento (.doc -> .docx) se necessário
            normalized_bytes, normalized_ext = DocumentConverter.normalize_document(
                file_bytes,
                file_ext
            )

            # Validar estrutura do documento
            is_valid, error_message = DocumentConverter.validate_document_structure(normalized_bytes)
            if not is_valid:
                logger.warning(f"Documento pode ter problemas de estrutura: {error_message}")

            # Processar documento normalizado
            doc = Document(io.BytesIO(normalized_bytes))

            # Extrair texto de todos os parágrafos
            text_content = []
            for paragraph in doc.paragraphs:
                text_content.append(paragraph.text)

            # Extrair tags usando TagProcessor
            all_text = ' '.join(text_content)
            detected_tags = list(set(TagProcessor.extract_tags(all_text)))

        except ValueError as e:
            logger.error(f"Erro ao processar documento: {e}")
            return jsonify({
                'error': f'Não foi possível processar o arquivo: {str(e)}'
            }), 400
        except Exception as e:
            logger.warning(f"Erro ao extrair tags do documento: {e}")
            detected_tags = []

        # Criar registro no banco
        template = Template(
            organization_id=organization_id,
            name=template_name,
            description=description,
            storage_type='uploaded',
            storage_file_url=storage_url,
            storage_file_key=storage_key,
            file_size=file_size,
            file_mime_type=content_type,
            detected_tags=detected_tags,
            created_by=g.user_id if hasattr(g, 'user_id') else None
        )

        db.session.add(template)
        db.session.commit()

        return jsonify({
            'success': True,
            'template': template_to_dict(template, include_tags=True)
        }), 201

    except Exception as e:
        logger.error(f"Erro ao fazer upload de template: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Erro ao fazer upload do arquivo',
            'message': str(e)
        }), 500
