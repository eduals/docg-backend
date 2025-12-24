"""
HubSpot Dynamic Data Routes - Endpoints para UI fields
"""

from flask import Blueprint, request, jsonify, g
from app.utils.auth import require_auth, require_org
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('hubspot_dynamic', __name__,
               url_prefix='/api/v1/apps/hubspot/dynamic-data')


@bp.route('/object-types', methods=['GET'])
@require_auth
@require_org
def get_object_types():
    """
    Retorna tipos de objetos disponíveis no HubSpot

    Response:
    {
        "options": [
            {"value": "deals", "label": "Deals", "description": "..."},
            ...
        ]
    }
    """
    object_types = [
        {
            "value": "contacts",
            "label": "Contacts",
            "description": "Individual people"
        },
        {
            "value": "companies",
            "label": "Companies",
            "description": "Business organizations"
        },
        {
            "value": "deals",
            "label": "Deals",
            "description": "Revenue opportunities"
        },
        {
            "value": "tickets",
            "label": "Tickets",
            "description": "Customer service requests"
        },
        {
            "value": "products",
            "label": "Products",
            "description": "Products or services you sell"
        },
        {
            "value": "line_items",
            "label": "Line Items",
            "description": "Individual items in deals"
        },
        {
            "value": "quotes",
            "label": "Quotes",
            "description": "Price quotes for deals"
        },
    ]

    return jsonify({"options": object_types})


@bp.route('/properties', methods=['GET'])
@require_auth
@require_org
def get_properties():
    """
    Retorna propriedades de um object type específico

    Query params:
    - object_type: deals, contacts, etc

    Response:
    {
        "properties": [
            {
                "name": "dealstage",
                "label": "Deal Stage",
                "type": "enumeration",
                "description": "..."
            },
            ...
        ]
    }
    """
    object_type = request.args.get('object_type')

    if not object_type:
        return jsonify({"error": "object_type is required"}), 400

    # Propriedades comuns por tipo de objeto
    properties_map = {
        "deals": [
            {"name": "dealname", "label": "Deal Name", "type": "string"},
            {"name": "amount", "label": "Amount", "type": "number"},
            {"name": "dealstage", "label": "Deal Stage", "type": "enumeration"},
            {"name": "pipeline", "label": "Pipeline", "type": "enumeration"},
            {"name": "closedate", "label": "Close Date", "type": "date"},
            {"name": "hs_priority", "label": "Priority", "type": "enumeration"},
        ],
        "contacts": [
            {"name": "firstname", "label": "First Name", "type": "string"},
            {"name": "lastname", "label": "Last Name", "type": "string"},
            {"name": "email", "label": "Email", "type": "string"},
            {"name": "phone", "label": "Phone", "type": "string"},
            {"name": "company", "label": "Company", "type": "string"},
            {"name": "jobtitle", "label": "Job Title", "type": "string"},
        ],
        "companies": [
            {"name": "name", "label": "Company Name", "type": "string"},
            {"name": "domain", "label": "Domain", "type": "string"},
            {"name": "industry", "label": "Industry", "type": "string"},
            {"name": "phone", "label": "Phone", "type": "string"},
            {"name": "city", "label": "City", "type": "string"},
            {"name": "state", "label": "State", "type": "string"},
        ],
        "tickets": [
            {"name": "subject", "label": "Subject", "type": "string"},
            {"name": "content", "label": "Content", "type": "text"},
            {"name": "hs_pipeline_stage", "label": "Status", "type": "enumeration"},
            {"name": "hs_ticket_priority", "label": "Priority", "type": "enumeration"},
        ]
    }

    properties = properties_map.get(object_type, [])

    return jsonify({"properties": properties})


@bp.route('/pipelines', methods=['GET'])
@require_auth
@require_org
def get_pipelines():
    """
    Retorna pipelines do HubSpot

    Response:
    {
        "pipelines": [
            {"id": "default", "label": "Sales Pipeline"},
            ...
        ]
    }
    """
    pipelines = [
        {"id": "default", "label": "Sales Pipeline"},
        {"id": "custom1", "label": "Enterprise Sales"},
    ]

    return jsonify({"pipelines": pipelines})
