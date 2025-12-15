from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import GlobalFieldMapping, User
from app.utils.auth import require_auth, require_org
import logging

logger = logging.getLogger(__name__)
global_field_mappings_bp = Blueprint('global_field_mappings', __name__, url_prefix='/api/v1/field-mappings')


@global_field_mappings_bp.route('/global', methods=['GET'])
@require_auth
@require_org
def list_global_field_mappings():
    """Lista mapeamentos globais da organização"""
    source_system = request.args.get('source_system')
    target_system = request.args.get('target_system')
    is_template = request.args.get('is_template', type=bool)
    
    query = GlobalFieldMapping.query.filter_by(organization_id=g.organization_id)
    
    if source_system:
        query = query.filter_by(source_system=source_system)
    if target_system:
        query = query.filter_by(target_system=target_system)
    if is_template is not None:
        query = query.filter_by(is_template=is_template)
    
    mappings = query.order_by(GlobalFieldMapping.created_at.desc()).all()
    
    return jsonify({
        'mappings': [mapping.to_dict() for mapping in mappings]
    })


@global_field_mappings_bp.route('/global', methods=['POST'])
@require_auth
@require_org
def create_global_field_mapping():
    """Cria novo mapeamento global"""
    data = request.get_json()
    
    required = ['name', 'source_system', 'target_system', 'mappings']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Obter usuário atual para created_by
    user_email = request.headers.get('X-User-Email') or request.args.get('user_email')
    user = None
    if user_email:
        user = User.query.filter_by(
            email=user_email,
            organization_id=g.organization_id
        ).first()
    
    mapping = GlobalFieldMapping(
        organization_id=g.organization_id,
        name=data['name'],
        source_system=data['source_system'],
        target_system=data['target_system'],
        mappings=data['mappings'],
        is_template=data.get('is_template', False),
        created_by=user.id if user else None
    )
    
    db.session.add(mapping)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mapping': mapping.to_dict()
    }), 201


@global_field_mappings_bp.route('/global/<mapping_id>', methods=['PUT'])
@require_auth
@require_org
def update_global_field_mapping(mapping_id):
    """Atualiza mapeamento global"""
    mapping = GlobalFieldMapping.query.filter_by(
        id=mapping_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'name' in data:
        mapping.name = data['name']
    if 'source_system' in data:
        mapping.source_system = data['source_system']
    if 'target_system' in data:
        mapping.target_system = data['target_system']
    if 'mappings' in data:
        mapping.mappings = data['mappings']
    if 'is_template' in data:
        mapping.is_template = data['is_template']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mapping': mapping.to_dict()
    })


@global_field_mappings_bp.route('/global/<mapping_id>', methods=['DELETE'])
@require_auth
@require_org
def delete_global_field_mapping(mapping_id):
    """Deleta mapeamento global"""
    mapping = GlobalFieldMapping.query.filter_by(
        id=mapping_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    db.session.delete(mapping)
    db.session.commit()
    
    return jsonify({'success': True})


@global_field_mappings_bp.route('/templates', methods=['GET'])
@require_auth
@require_org
def list_field_mapping_templates():
    """Lista templates de mapeamento"""
    source_system = request.args.get('source_system')
    target_system = request.args.get('target_system')
    
    query = GlobalFieldMapping.query.filter_by(
        organization_id=g.organization_id,
        is_template=True
    )
    
    if source_system:
        query = query.filter_by(source_system=source_system)
    if target_system:
        query = query.filter_by(target_system=target_system)
    
    templates = query.order_by(GlobalFieldMapping.created_at.desc()).all()
    
    return jsonify({
        'templates': [template.to_dict() for template in templates]
    })
