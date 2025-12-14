"""
Script para migrar workflows existentes de 'clicksign' para 'signature'.
"""
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import db
from app.models import WorkflowNode

app = create_app()

def migrate_signature_nodes():
    """Migra nodes clicksign para signature"""
    with app.app_context():
        # Buscar todos os nodes clicksign
        clicksign_nodes = WorkflowNode.query.filter_by(node_type='clicksign').all()
        
        migrated_count = 0
        for node in clicksign_nodes:
            config = node.config or {}
            
            # Se não tem provider no config, adicionar
            if 'provider' not in config:
                config['provider'] = 'clicksign'
                node.config = config
                node.node_type = 'signature'
                migrated_count += 1
                print(f"Migrado node {node.id}: clicksign -> signature (provider=clicksign)")
            else:
                # Já tem provider, apenas atualizar node_type
                node.node_type = 'signature'
                migrated_count += 1
                print(f"Migrado node {node.id}: clicksign -> signature (provider já configurado)")
        
        db.session.commit()
        print(f"\nMigração concluída: {migrated_count} nodes migrados")
        return migrated_count

if __name__ == '__main__':
    migrate_signature_nodes()
