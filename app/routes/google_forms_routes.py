"""
Rotas para Google Forms - Listagem de formulários e campos.
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.routes.google_drive_routes import get_google_credentials
from app.services.data_sources.google_forms import GoogleFormsDataSource
from app.utils.auth import require_auth, require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
import logging

logger = logging.getLogger(__name__)
google_forms_bp = Blueprint('google_forms', __name__, url_prefix='/api/v1/google-forms')


@google_forms_bp.route('/forms', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def list_forms():
    """
    Lista formulários do usuário.
    
    Retorna lista de formulários Google Forms acessíveis pelo usuário.
    """
    try:
        organization_id = g.organization_id
        
        # Obter credenciais Google da organização
        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        # Criar DataSource
        data_source = GoogleFormsDataSource(credentials=google_creds)
        
        # Listar formulários
        forms = data_source.list_forms()
        
        return jsonify({
            'success': True,
            'forms': forms
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao listar formulários: {str(e)}")
        return jsonify({
            'error': f'Erro ao listar formulários: {str(e)}'
        }), 500


@google_forms_bp.route('/forms/<form_id>/fields', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_form_fields(form_id):
    """
    Lista campos/propriedades de um formulário.
    
    Retorna lista de campos disponíveis para mapeamento.
    
    Args:
        form_id: ID do formulário Google Forms
    """
    try:
        organization_id = g.organization_id
        
        # Obter credenciais Google da organização
        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        # Criar DataSource
        data_source = GoogleFormsDataSource(credentials=google_creds)
        
        # Buscar campos do formulário
        fields = data_source.get_form_fields(form_id)
        
        return jsonify({
            'success': True,
            'form_id': form_id,
            'fields': fields
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao buscar campos do formulário: {str(e)}")
        return jsonify({
            'error': f'Erro ao buscar campos do formulário: {str(e)}'
        }), 500
