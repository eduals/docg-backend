"""
Endpoint de health check geral da API
"""
from flask import Blueprint, jsonify
from datetime import datetime
from sqlalchemy import text
from app.database import db

bp = Blueprint('health', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health_check():
    """Healthcheck endpoint para verificar se a API está online e o banco de dados está acessível"""
    try:
        # Testar conexão com o banco de dados
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'status': 'healthy',
            'message': 'API is online and database connection is working',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': 'API is online but database connection failed',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 503

