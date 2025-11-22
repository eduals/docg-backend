from flask import Blueprint, request, jsonify
from app.database import db
from app.models import EnvelopeRelation, EnvelopeExecutionLog
from app.auth import require_auth
from app.utils.auth import require_org
from app.services.envelope_creation_service import EnvelopeCreationService
from threading import Thread
import uuid
from datetime import datetime

bp = Blueprint('envelopes', __name__, url_prefix='/api/v1/envelopes')

@bp.route('', methods=['GET'])
@require_auth
def list_envelopes():
    """Listar envelopes de um objeto"""
    try:
        portal_id = request.args.get('portal_id')
        hubspot_object_type = request.args.get('hubspot_object_type')
        hubspot_object_id = request.args.get('hubspot_object_id')
        
        if not portal_id:
            return jsonify({
                'error': 'portal_id is required'
            }), 400
        
        query = EnvelopeRelation.query.filter_by(portal_id=portal_id)
        
        if hubspot_object_type:
            query = query.filter_by(hubspot_object_type=hubspot_object_type)
        
        if hubspot_object_id:
            query = query.filter_by(hubspot_object_id=hubspot_object_id)
        
        relations = query.order_by(EnvelopeRelation.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [relation.to_dict() for relation in relations]
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/create', methods=['POST'])
@require_org
def create_envelope():
    """Criar envelope completo (processo assíncrono)"""
    try:
        organization_id = g.organization_id
        data = request.get_json()
        
        required_fields = ['hubspot_object_type', 'hubspot_object_id', 
                          'envelope_name', 'documents', 'recipients']
        
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'{field} is required'
                }), 400
        
        # Buscar portal_id via DataSourceConnection para EnvelopeExecutionLog (temporário)
        from app.models import DataSourceConnection
        connection = DataSourceConnection.query.filter_by(
            organization_id=organization_id,
            source_type='hubspot'
        ).first()
        portal_id = connection.config.get('portal_id') if connection and connection.config else None
        
        # Gerar execution_id único
        execution_id = str(uuid.uuid4())
        
        # Criar logs iniciais para todas as etapas
        steps = [
            {'name': 'Creating envelope', 'order': 1},
            {'name': 'Adding documents', 'order': 2},
            {'name': 'Applying field mappings', 'order': 3},
            {'name': 'Adding signers', 'order': 4},
            {'name': 'Saving to HubSpot', 'order': 5},
            {'name': 'Sending envelope', 'order': 6}
        ]
        
        for step in steps:
            log = EnvelopeExecutionLog(
                portal_id=portal_id or str(organization_id),  # Temporário: usar portal_id se disponível
                execution_id=execution_id,
                step_name=step['name'],
                step_status='pending',
                step_order=step['order']
            )
            db.session.add(log)
        
        db.session.commit()
        
        # Iniciar processamento assíncrono em thread separada
        from threading import Thread
        from app.services.envelope_creation_service import EnvelopeCreationService
        
        def process_envelope():
            try:
                service = EnvelopeCreationService(organization_id, execution_id)
                service.process_envelope_creation(data)
            except Exception as e:
                # Log de erro final
                log = EnvelopeExecutionLog.query.filter_by(
                    execution_id=execution_id,
                    step_name='Sending envelope'
                ).first()
                if log:
                    log.step_status = 'error'
                    log.error_message = f"Fatal error: {str(e)}"
                    db.session.commit()
        
        thread = Thread(target=process_envelope)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'execution_id': execution_id
        }), 202
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/execution/<execution_id>/progress', methods=['GET'])
@require_auth
def get_execution_progress(execution_id):
    """Obter progresso da execução"""
    try:
        logs = EnvelopeExecutionLog.query.filter_by(
            execution_id=execution_id
        ).order_by(EnvelopeExecutionLog.step_order).all()
        
        if not logs:
            return jsonify({
                'error': 'Execution not found'
            }), 404
        
        # Determinar status geral
        status = 'pending'
        if any(log.step_status == 'in_progress' for log in logs):
            status = 'in_progress'
        elif all(log.step_status in ['completed', 'error'] for log in logs):
            if any(log.step_status == 'error' for log in logs):
                status = 'error'
            else:
                status = 'completed'
        
        # Obter envelope_id se disponível
        envelope_id = None
        envelope_log = next((log for log in logs if log.envelope_id), None)
        if envelope_log:
            envelope_id = envelope_log.envelope_id
        
        steps = [log.to_dict() for log in logs]
        
        return jsonify({
            'success': True,
            'execution_id': execution_id,
            'status': status,
            'steps': steps,
            'envelope_id': envelope_id,
            'created_at': logs[0].created_at.isoformat() if logs else None
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

