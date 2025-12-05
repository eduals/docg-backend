"""
Helper functions para operações comuns
"""
from app.models import DataSourceConnection, Organization, User
from app.database import db
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta
from app.config import Config


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


def create_organization_from_hubspot_context(portal_id, user_email, user_id=None, app_id=None):
    """
    Cria automaticamente organização, usuário e conexão HubSpot quando app é instalado.
    
    Args:
        portal_id: portal_id do HubSpot
        user_email: email do usuário que instalou o app
        user_id: hubspot_user_id (opcional)
        app_id: app_id do HubSpot (opcional)
    
    Returns:
        organization_id (UUID) da organização criada ou encontrada
    """
    # 1. Verificar se já existe organização para este portal_id
    existing_org_id = get_organization_id_from_portal_id(portal_id)
    if existing_org_id:
        return existing_org_id
    
    # 2. Criar Organization
    org_name = f"HubSpot Portal {portal_id}"
    slug = f"portal-{portal_id}"
    # Verificar se slug já existe
    counter = 1
    while Organization.query.filter_by(slug=slug).first():
        slug = f"portal-{portal_id}-{counter}"
        counter += 1
    
    trial_expires_at = datetime.utcnow() + timedelta(days=Config.TRIAL_DAYS)
    
    org = Organization(
        name=org_name,
        slug=slug,
        plan='free',
        billing_email=user_email,
        trial_expires_at=trial_expires_at,
        is_active=True
    )
    db.session.add(org)
    db.session.flush()  # Para obter o ID
    
    # 3. Criar User admin
    user = User(
        organization_id=org.id,
        email=user_email,
        name=user_email.split('@')[0],  # Nome baseado no email
        role='admin',
        hubspot_user_id=user_id
    )
    db.session.add(user)
    
    # 4. Criar DataSourceConnection para HubSpot
    connection = DataSourceConnection(
        organization_id=org.id,
        source_type='hubspot',
        name=f"HubSpot Portal {portal_id}",
        config={'portal_id': str(portal_id), 'app_id': str(app_id) if app_id else None},
        status='active'
    )
    db.session.add(connection)
    
    db.session.commit()
    
    return org.id

