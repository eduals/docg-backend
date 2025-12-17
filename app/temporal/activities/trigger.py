"""
Activity de Trigger - Extração de dados de fontes.
"""
import logging
from typing import Dict, Any
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def execute_trigger_node(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa node de trigger (extração de dados).
    
    Suporta:
    - hubspot: Extrai dados de objeto HubSpot
    - webhook: Usa dados já presentes no trigger_data
    - google-forms: (TODO)
    
    Args:
        data: {
            execution_id,
            node: {id, node_type, config, ...},
            trigger_data: dados do trigger original,
            workflow_id: ID do workflow,
            organization_id: ID da organização
        }
    
    Returns:
        {source_data: {...}, source_object_id, source_object_type}
    """
    from app.database import db
    from app.models import DataSourceConnection
    from app.services.data_sources.hubspot import HubSpotDataSource
    from flask import current_app
    
    node = data['node']
    config = node.get('config', {})
    trigger_data = data.get('trigger_data', {})
    node_type = node.get('node_type', 'hubspot')
    
    activity.logger.info(f"Executando trigger node {node['id']} tipo {node_type}")
    
    with current_app.app_context():
        # Determinar tipo de trigger
        if node_type == 'webhook':
            # Webhook trigger - dados já vêm no trigger_data
            # Priorizar source_data mapeado, senão usar payload original
            source_data = trigger_data.get('source_data') or trigger_data.get('payload', trigger_data)
            return {
                'source_data': source_data,
                'source_object_id': trigger_data.get('source_object_id', 'webhook'),
                'source_object_type': trigger_data.get('source_object_type', 'webhook')
            }
        
        elif node_type == 'google-forms':
            # Google Forms trigger - buscar respostas do formulário
            form_id = config.get('form_id')
            response_id = config.get('response_id')  # Opcional: resposta específica
            
            if not form_id:
                raise ValueError('form_id não configurado no Google Forms node')
            
            # Buscar credenciais Google da organização
            from app.routes.google_drive_routes import get_google_credentials
            from app.models import Workflow
            from app.services.data_sources.google_forms import GoogleFormsDataSource
            
            # workflow_id e organization_id vêm do data passado pelo workflow
            workflow_id = data.get('workflow_id')
            organization_id = data.get('organization_id')
            
            if not workflow_id:
                raise ValueError('workflow_id não fornecido')
            
            if not organization_id:
                # Fallback: buscar do workflow
                from app.models import Workflow
                workflow = Workflow.query.get(workflow_id)
                if not workflow:
                    raise ValueError(f'Workflow não encontrado: {workflow_id}')
                organization_id = str(workflow.organization_id)
            
            google_creds = get_google_credentials(organization_id)
            if not google_creds:
                raise ValueError('Credenciais Google não configuradas para esta organização')
            
            # Criar DataSource e buscar respostas
            data_source = GoogleFormsDataSource(credentials=google_creds)
            source_data = data_source.get_form_responses(form_id, response_id)
            
            # Determinar source_object_id (response_id se fornecido, senão usar form_id)
            if response_id:
                source_object_id = response_id
            else:
                # Usar form_id como base (será substituído pela resposta real)
                source_object_id = form_id
            
            activity.logger.info(
                f"Google Forms trigger executado: formulário {form_id} "
                f"com {len(source_data)} campos mapeados"
            )
            
            return {
                'source_data': source_data,
                'source_object_id': source_object_id,
                'source_object_type': 'form_response'
            }
        
        else:
            # HubSpot trigger (default)
            source_connection_id = config.get('source_connection_id')
            source_object_type = config.get('source_object_type') or trigger_data.get('source_object_type')
            source_object_id = trigger_data.get('source_object_id')
            
            if not source_connection_id:
                raise ValueError('source_connection_id não configurado no trigger node')
            
            if not source_object_id:
                raise ValueError('source_object_id não encontrado no trigger_data')
            
            # Buscar conexão
            connection = DataSourceConnection.query.get(source_connection_id)
            if not connection:
                raise ValueError(f'Conexão não encontrada: {source_connection_id}')
            
            if connection.source_type != 'hubspot':
                raise ValueError(f'Tipo de conexão não suportado: {connection.source_type}')
            
            # Extrair dados do HubSpot
            data_source = HubSpotDataSource(connection)
            source_data = data_source.get_object_data(
                source_object_type,
                source_object_id
            )
            
            # Normalizar dados (mover properties para nível raiz)
            if isinstance(source_data, dict) and 'properties' in source_data:
                properties = source_data.pop('properties', {})
                if isinstance(properties, dict):
                    source_data.update(properties)
            
            activity.logger.info(
                f"HubSpot trigger executado: {source_object_type} {source_object_id} "
                f"com {len(source_data)} campos"
            )
            
            return {
                'source_data': source_data,
                'source_object_id': source_object_id,
                'source_object_type': source_object_type
            }

