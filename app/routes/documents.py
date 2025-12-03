from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import (
    GeneratedDocument, Workflow, Template, 
    DataSourceConnection, Organization
)
from app.services.document_generation import DocumentGenerator
from app.services.data_sources.hubspot import HubSpotDataSource
from app.utils.auth import require_auth, require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
from app.routes.google_drive_routes import get_google_credentials
import logging
import uuid

logger = logging.getLogger(__name__)
documents_bp = Blueprint('documents', __name__, url_prefix='/api/v1/documents')


@documents_bp.route('', methods=['GET'])
@flexible_hubspot_auth
@require_org
def list_documents():
    """Lista documentos gerados da organização"""
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    workflow_id = request.args.get('workflow_id')
    object_type = request.args.get('object_type')
    object_id = request.args.get('object_id')
    
    query = GeneratedDocument.query.filter_by(organization_id=org_id)
    
    if status:
        query = query.filter_by(status=status)
    if workflow_id:
        query = query.filter_by(workflow_id=workflow_id)
    if object_type:
        query = query.filter_by(source_object_type=object_type)
    if object_id:
        query = query.filter_by(source_object_id=object_id)
    
    query = query.order_by(GeneratedDocument.created_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'documents': [doc_to_dict(d) for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })


@documents_bp.route('/<document_id>', methods=['GET'])
@require_auth
@require_org
def get_document(document_id):
    """Retorna detalhes de um documento"""
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()
    
    return jsonify(doc_to_dict(doc, include_details=True))


@documents_bp.route('/generate', methods=['POST'])
@flexible_hubspot_auth
@require_org
def generate_document():
    """
    Gera um novo documento.
    
    Body:
    {
        "workflow_id": "uuid",
        "source_object_id": "123",
        "source_data": {...}  // opcional, se não passar busca automaticamente
    }
    """
    data = request.get_json()
    
    workflow_id = data.get('workflow_id')
    source_object_id = data.get('source_object_id')
    source_data = data.get('source_data')
    
    if not workflow_id or not source_object_id:
        return jsonify({'error': 'workflow_id e source_object_id são obrigatórios'}), 400
    
    # Buscar workflow
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Se não passou source_data, busca da fonte
    if not source_data:
        connection = workflow.source_connection
        if not connection:
            return jsonify({'error': 'Conexão de dados não configurada'}), 400
        
        if connection.source_type == 'hubspot':
            # Extrair propriedades necessárias dos field_mappings
            additional_properties = []
            for mapping in workflow.field_mappings:
                source_field = mapping.source_field
                # Apenas propriedades diretas (sem dot notation) precisam ser incluídas
                # Campos com dot notation (ex: associations.company.name) são acessados via associações
                if source_field and '.' not in source_field:
                    additional_properties.append(source_field)
            
            data_source = HubSpotDataSource(connection)
            source_data = data_source.get_object_data(
                workflow.source_object_type,
                source_object_id,
                additional_properties=additional_properties if additional_properties else None
            )
        else:
            return jsonify({'error': f'Fonte {connection.source_type} não suportada ainda'}), 400
    
    # Gerar documento
    try:
        # Obter credentials do Google usando organization_id
        organization_id = g.organization_id
        # Converter organization_id para UUID se for string para garantir consistência
        org_id_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        
        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({'error': 'Credenciais do Google não configuradas'}), 400
        
        generator = DocumentGenerator(google_creds)
        doc = generator.generate_from_workflow(
            workflow=workflow,
            source_data=source_data,
            source_object_id=source_object_id,
            user_id=data.get('user_id'),
            organization_id=org_id_uuid
        )
        
        return jsonify({
            'success': True,
            'document': doc_to_dict(doc)
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao gerar documento: {str(e)}")
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/<document_id>/regenerate', methods=['POST'])
@require_auth
@require_org
def regenerate_document(document_id):
    """Regenera um documento existente"""
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()
    
    # Usa os mesmos dados do documento original
    try:
        organization_id = g.organization_id
        # Converter organization_id para UUID se for string para garantir consistência
        org_id_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        
        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({'error': 'Credenciais do Google não configuradas'}), 400
        
        generator = DocumentGenerator(google_creds)
        
        new_doc = generator.generate_from_workflow(
            workflow=doc.workflow,
            source_data=doc.generated_data,
            source_object_id=doc.source_object_id,
            user_id=request.get_json().get('user_id') if request.is_json else None,
            organization_id=org_id_uuid
        )
        
        return jsonify({
            'success': True,
            'document': doc_to_dict(new_doc)
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao regenerar documento: {str(e)}")
        return jsonify({'error': str(e)}), 500


@documents_bp.route('/<document_id>', methods=['DELETE'])
@require_auth
@require_org
def delete_document(document_id):
    """Deleta um documento gerado"""
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()
    
    # TODO: Opcionalmente deletar do Google Drive também
    
    db.session.delete(doc)
    db.session.commit()
    
    return jsonify({'success': True})


def doc_to_dict(doc: GeneratedDocument, include_details: bool = False) -> dict:
    """Converte documento para dicionário"""
    # Usar o método to_dict do modelo que já inclui informações do HubSpot
    result = doc.to_dict(include_details=include_details)
    return result

