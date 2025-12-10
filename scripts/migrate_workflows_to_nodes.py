"""
Script de migração para converter workflows existentes para estrutura de nodes.

Este script:
1. Busca todos os workflows existentes
2. Cria trigger node para cada workflow
3. Cria google-docs node com configurações do workflow
4. Migra field_mappings para o node google-docs
5. Mantém workflows legados funcionando durante transição
"""
import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.database import db
from app.models import Workflow, WorkflowNode, WorkflowFieldMapping
from datetime import datetime

def migrate_workflows():
    """Migra workflows existentes para estrutura de nodes"""
    app = create_app()
    
    with app.app_context():
        # Buscar todos os workflows
        workflows = Workflow.query.all()
        
        print(f"Encontrados {len(workflows)} workflows para migrar")
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for workflow in workflows:
            try:
                # Verificar se já tem nodes
                existing_nodes = WorkflowNode.query.filter_by(workflow_id=workflow.id).count()
                if existing_nodes > 0:
                    print(f"  Workflow {workflow.id} já possui nodes, pulando...")
                    skipped += 1
                    continue
                
                print(f"  Migrando workflow {workflow.id} ({workflow.name})...")
                
                # 1. Criar trigger node
                trigger_config = {
                    'trigger_type': workflow.trigger_type or 'manual',
                    'source_connection_id': str(workflow.source_connection_id) if workflow.source_connection_id else None,
                    'source_object_type': workflow.source_object_type,
                    'trigger_config': workflow.trigger_config or {}
                }
                
                trigger_node = WorkflowNode(
                    workflow_id=workflow.id,
                    node_type='trigger',
                    position=1,
                    parent_node_id=None,
                    config=trigger_config,
                    status='configured' if trigger_config.get('source_connection_id') else 'draft'
                )
                db.session.add(trigger_node)
                db.session.flush()
                
                # 2. Criar google-docs node se houver template
                if workflow.template_id:
                    # Buscar field_mappings do workflow
                    field_mappings = list(workflow.field_mappings)
                    field_mappings_config = [
                        {
                            'template_tag': m.template_tag,
                            'source_field': m.source_field,
                            'transform_type': m.transform_type,
                            'transform_config': m.transform_config,
                            'default_value': m.default_value
                        }
                        for m in field_mappings
                    ]
                    
                    google_docs_config = {
                        'template_id': str(workflow.template_id),
                        'output_name_template': workflow.output_name_template or '{{object_type}} - {{timestamp}}',
                        'output_folder_id': workflow.output_folder_id,
                        'create_pdf': workflow.create_pdf,
                        'remove_branding': False,
                        'field_mappings': field_mappings_config
                    }
                    
                    google_docs_node = WorkflowNode(
                        workflow_id=workflow.id,
                        node_type='google-docs',
                        position=2,
                        parent_node_id=trigger_node.id,
                        config=google_docs_config,
                        status='configured'
                    )
                    db.session.add(google_docs_node)
                
                db.session.commit()
                migrated += 1
                print(f"    ✓ Migrado com sucesso")
                
            except Exception as e:
                db.session.rollback()
                print(f"    ✗ Erro: {str(e)}")
                errors += 1
                continue
        
        print(f"\nMigração concluída:")
        print(f"  Migrados: {migrated}")
        print(f"  Pulados: {skipped}")
        print(f"  Erros: {errors}")


if __name__ == '__main__':
    migrate_workflows()
