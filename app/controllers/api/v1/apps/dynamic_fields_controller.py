"""
Dynamic Fields Controller - Endpoint para buscar campos dinâmicos de apps.

Permite que o frontend busque campos que dependem de seleções anteriores.
Por exemplo: campos de um objeto HubSpot baseado no tipo selecionado.
"""

from flask import jsonify, request, g
import asyncio
from . import apps_bp


@apps_bp.route('/<app_key>/dynamic-fields/<definition_key>', methods=['GET'])
def get_dynamic_fields(app_key: str, definition_key: str):
    """
    Obtém campos dinâmicos de um app.

    Query params:
        connection_id: ID da conexão para autenticação (opcional)
        ... outros params são passados como context

    Returns:
        {
            "fields": [
                {
                    "key": "email",
                    "label": "Email",
                    "type": "string",
                    "required": false,
                    ...
                }
            ]
        }
    """
    from app.apps import AppRegistry

    # Obter app
    app = AppRegistry.get(app_key)
    if not app:
        return jsonify({'error': f"App '{app_key}' not found"}), 404

    # Verificar se definition existe
    definition = app.get_dynamic_fields_definition(definition_key)
    if not definition:
        return jsonify({'error': f"Dynamic fields '{definition_key}' not found in app '{app_key}'"}), 404

    # Extrair connection_id e context dos query params
    connection_id = request.args.get('connection_id')
    context = {
        k: v for k, v in request.args.items()
        if k != 'connection_id'
    }

    # Executar async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        fields = loop.run_until_complete(
            app.fetch_dynamic_fields(
                key=definition_key,
                connection_id=connection_id,
                context=context,
            )
        )
        return jsonify({'fields': fields})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        loop.close()


@apps_bp.route('/<app_key>/dynamic-fields', methods=['GET'])
def list_dynamic_fields_definitions(app_key: str):
    """
    Lista definições de campos dinâmicos disponíveis em um app.

    Returns:
        {
            "definitions": [
                {
                    "key": "objectFields",
                    "depends_on": ["object_type"]
                }
            ]
        }
    """
    from app.apps import AppRegistry

    app = AppRegistry.get(app_key)
    if not app:
        return jsonify({'error': f"App '{app_key}' not found"}), 404

    definitions = app.get_dynamic_fields_list()
    return jsonify({
        'definitions': [d.to_dict() for d in definitions]
    })
