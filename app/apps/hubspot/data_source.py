"""
HubSpot Data Source - Wrapper para o serviço existente.

Este módulo fornece acesso ao HubSpotDataSource existente
através da nova estrutura de apps.

NOTA: Importa diretamente do serviço existente para manter
backward compatibility.
"""

# Re-exportar do serviço existente
from app.services.data_sources.hubspot import HubSpotDataSource

# Re-exportar para conveniência
__all__ = ['HubSpotDataSource']


# Helper functions que usam o DataSource
async def get_object_data(
    connection_id: str,
    object_type: str,
    object_id: str,
    properties: list = None,
) -> dict:
    """
    Busca dados de um objeto HubSpot.

    Args:
        connection_id: ID da DataSourceConnection
        object_type: Tipo do objeto (contact, deal, company)
        object_id: ID do objeto
        properties: Lista de propriedades adicionais

    Returns:
        Dict com dados do objeto
    """
    from app.models import DataSourceConnection

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    data_source = HubSpotDataSource(connection)
    return data_source.get_object_data(object_type, object_id, properties)


async def list_objects(
    connection_id: str,
    object_type: str,
    limit: int = 10,
    properties: list = None,
) -> list:
    """
    Lista objetos HubSpot.

    Args:
        connection_id: ID da DataSourceConnection
        object_type: Tipo do objeto
        limit: Limite de resultados
        properties: Propriedades a incluir

    Returns:
        Lista de objetos
    """
    from app.models import DataSourceConnection

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    data_source = HubSpotDataSource(connection)
    return data_source.list_objects(object_type, limit=limit, properties=properties)
