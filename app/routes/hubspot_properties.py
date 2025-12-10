"""
Rotas para propriedades do HubSpot com cache.
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import HubSpotPropertyCache, DataSourceConnection
from app.services.data_sources.hubspot import HubSpotDataSource
from app.utils.auth import require_auth, require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
import logging
import uuid

logger = logging.getLogger(__name__)
hubspot_properties_bp = Blueprint('hubspot_properties', __name__, url_prefix='/api/v1/hubspot/properties')


@hubspot_properties_bp.route('', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def list_properties():
    """
    Lista propriedades do HubSpot para um tipo de objeto.
    
    Query params:
    - object_type: deal, contact, company, ticket (obrigatório)
    - use_cache: true/false (default: true)
    """
    org_id = g.organization_id
    object_type = request.args.get('object_type')
    
    if not object_type:
        return jsonify({'error': 'object_type é obrigatório'}), 400
    
    valid_types = ['deal', 'contact', 'company', 'ticket']
    if object_type not in valid_types:
        return jsonify({
            'error': f'object_type deve ser um de: {", ".join(valid_types)}'
        }), 400
    
    use_cache = request.args.get('use_cache', 'true').lower() == 'true'
    
    # Buscar do cache se disponível
    if use_cache:
        cached_properties = HubSpotPropertyCache.query.filter_by(
            organization_id=org_id,
            object_type=object_type
        ).all()
        
        if cached_properties:
            return jsonify({
                'properties': [prop.to_dict() for prop in cached_properties],
                'cached': True,
                'cached_at': cached_properties[0].cached_at.isoformat() if cached_properties else None
            })
    
    # Buscar do HubSpot
    try:
        # Buscar conexão HubSpot da organização
        connection = DataSourceConnection.query.filter_by(
            organization_id=org_id,
            source_type='hubspot',
            status='active'
        ).first()
        
        if not connection:
            return jsonify({
                'error': 'Conexão HubSpot não encontrada ou não está ativa'
            }), 400
        
        # Buscar propriedades do HubSpot
        data_source = HubSpotDataSource(connection)
        properties = data_source.get_object_properties(object_type)
        
        # Salvar no cache
        # Limpar cache antigo
        HubSpotPropertyCache.query.filter_by(
            organization_id=org_id,
            object_type=object_type
        ).delete()
        
        # Criar novos registros
        for prop in properties:
            cached_prop = HubSpotPropertyCache(
                organization_id=org_id,
                object_type=object_type,
                property_name=prop.get('name', ''),
                label=prop.get('label', prop.get('name', '')),
                type=prop.get('type', 'string'),
                options=prop.get('options')
            )
            db.session.add(cached_prop)
        
        db.session.commit()
        
        return jsonify({
            'properties': properties,
            'cached': False
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar propriedades do HubSpot: {str(e)}")
        return jsonify({
            'error': f'Erro ao buscar propriedades: {str(e)}'
        }), 500


@hubspot_properties_bp.route('/refresh', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
def refresh_properties():
    """
    Força atualização do cache de propriedades.
    
    Body (opcional):
    {
        "object_type": "deal"  // Se não fornecido, atualiza todos
    }
    """
    org_id = g.organization_id
    data = request.get_json() or {}
    object_type = data.get('object_type')
    
    valid_types = ['deal', 'contact', 'company', 'ticket']
    object_types = [object_type] if object_type else valid_types
    
    if object_type and object_type not in valid_types:
        return jsonify({
            'error': f'object_type deve ser um de: {", ".join(valid_types)}'
        }), 400
    
    # Buscar conexão HubSpot
    connection = DataSourceConnection.query.filter_by(
        organization_id=org_id,
        source_type='hubspot',
        status='active'
    ).first()
    
    if not connection:
        return jsonify({
            'error': 'Conexão HubSpot não encontrada ou não está ativa'
        }), 400
    
    data_source = HubSpotDataSource(connection)
    updated_count = 0
    
    for obj_type in object_types:
        try:
            # Buscar propriedades do HubSpot
            properties = data_source.get_object_properties(obj_type)
            
            # Limpar cache antigo
            HubSpotPropertyCache.query.filter_by(
                organization_id=org_id,
                object_type=obj_type
            ).delete()
            
            # Criar novos registros
            for prop in properties:
                cached_prop = HubSpotPropertyCache(
                    organization_id=org_id,
                    object_type=obj_type,
                    property_name=prop.get('name', ''),
                    label=prop.get('label', prop.get('name', '')),
                    type=prop.get('type', 'string'),
                    options=prop.get('options')
                )
                db.session.add(cached_prop)
            
            updated_count += len(properties)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar propriedades para {obj_type}: {str(e)}")
            continue
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'object_types': object_types
    })
