"""
Helper functions para operações comuns
"""
from app.models import DataSourceConnection
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import JSONB


def get_hubspot_portal_id(organization_id):
    """
    Busca portal_id do HubSpot para uma organização.
    
    Args:
        organization_id: UUID da organização
        
    Returns:
        portal_id (string) ou None se não encontrado
    """
    connection = DataSourceConnection.query.filter_by(
        organization_id=organization_id,
        source_type='hubspot'
    ).first()
    
    return connection.portal_id if connection else None


def get_organization_id_from_portal_id(portal_id):
    """
    Busca organization_id a partir de um portal_id do HubSpot.
    
    Args:
        portal_id: portal_id do HubSpot
        
    Returns:
        organization_id (UUID) ou None se não encontrado
    """
    # Buscar connection onde config.portal_id = portal_id
    # Usar JSONB operator para buscar no campo config
    from sqlalchemy import text
    from app.database import db
    
    result = db.session.execute(
        text("""
            SELECT organization_id 
            FROM data_source_connections 
            WHERE source_type = 'hubspot' 
            AND (config->>'portal_id')::text = :portal_id
            LIMIT 1
        """),
        {'portal_id': str(portal_id)}
    ).fetchone()
    
    return result[0] if result else None

