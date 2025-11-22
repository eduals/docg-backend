"""
Script de migração de Account para Organization

Este script migra dados da tabela accounts para organizations e cria
DataSourceConnections apropriadas.

Uso:
    python -m scripts.migrate_account_to_organization
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app import create_app
from app.config import Config
from app.database import db
from app.models import Account
from app.models import Organization, DataSourceConnection
import uuid
import re


def normalize_slug(name):
    """Normaliza um nome para slug"""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:100]  # Limitar tamanho


def migrate_accounts():
    """Migra todos os accounts para organizations"""
    app = create_app(Config)
    
    with app.app_context():
        accounts = Account.query.all()
        
        if not accounts:
            print("Nenhum account encontrado para migrar.")
            return
        
        print(f"Encontrados {len(accounts)} accounts para migrar.")
        
        migrated = 0
        errors = 0
        
        for account in accounts:
            try:
                # Buscar ou criar Organization baseada no portal_id
                # Primeiro, tentar buscar por slug baseado no portal_id
                slug = f"portal-{account.portal_id}"
                org = Organization.query.filter_by(slug=slug).first()
                
                if not org:
                    # Criar nova Organization
                    org_name = f"Portal {account.portal_id}"
                    org = Organization(
                        name=org_name,
                        slug=slug,
                        plan='free',
                        trial_expires_at=account.trial_expires_at,
                        plan_expires_at=account.plan_expires_at,
                        is_active=account.is_active,
                        clicksign_api_key=account.clicksign_api_key  # Temporário
                    )
                    db.session.add(org)
                    db.session.flush()  # Para obter o ID
                    print(f"  ✓ Criada Organization {org.id} para portal_id {account.portal_id}")
                else:
                    # Atualizar Organization existente
                    org.trial_expires_at = account.trial_expires_at
                    org.plan_expires_at = account.plan_expires_at
                    org.is_active = account.is_active
                    if account.clicksign_api_key and not org.clicksign_api_key:
                        org.clicksign_api_key = account.clicksign_api_key
                    print(f"  ✓ Atualizada Organization {org.id} para portal_id {account.portal_id}")
                
                # Criar DataSourceConnection para HubSpot
                hubspot_connection = DataSourceConnection.query.filter_by(
                    organization_id=org.id,
                    source_type='hubspot'
                ).first()
                
                if not hubspot_connection:
                    hubspot_connection = DataSourceConnection(
                        organization_id=org.id,
                        source_type='hubspot',
                        name=f"HubSpot Portal {account.portal_id}",
                        config={'portal_id': account.portal_id},
                        status='active'
                    )
                    db.session.add(hubspot_connection)
                    print(f"    ✓ Criada DataSourceConnection HubSpot para portal_id {account.portal_id}")
                
                # Criar DataSourceConnection para ClickSign (se tiver API key)
                if account.clicksign_api_key:
                    clicksign_connection = DataSourceConnection.query.filter_by(
                        organization_id=org.id,
                        source_type='clicksign'
                    ).first()
                    
                    if not clicksign_connection:
                        clicksign_connection = DataSourceConnection(
                            organization_id=org.id,
                            source_type='clicksign',
                            name="ClickSign Integration",
                            credentials={'clicksign_api_key': account.clicksign_api_key},
                            status='active'
                        )
                        db.session.add(clicksign_connection)
                        print(f"    ✓ Criada DataSourceConnection ClickSign para portal_id {account.portal_id}")
                
                db.session.commit()
                migrated += 1
                
            except Exception as e:
                db.session.rollback()
                print(f"  ✗ Erro ao migrar account {account.portal_id}: {str(e)}")
                errors += 1
                continue
        
        print(f"\nMigração concluída:")
        print(f"  - Migrados: {migrated}")
        print(f"  - Erros: {errors}")
        print(f"\nPróximos passos:")
        print(f"  1. Verificar se todos os dados foram migrados corretamente")
        print(f"  2. Executar migração de GoogleOAuthToken e GoogleDriveConfig")
        print(f"  3. Após confirmação, remover tabela accounts")


if __name__ == '__main__':
    migrate_accounts()

