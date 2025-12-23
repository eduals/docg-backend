"""
Template Tags Controller.
"""

from flask import jsonify, g
from app.models import Template


def get_template_tags(template_id: str):
    """
    Retorna tags detectadas no template.

    Retorna tags no formato:
    {
        "tags": [
            {
                "tag": "{{deal.dealname}}",
                "type": "hubspot",
                "object_type": "deal",
                "property": "dealname"
            },
            {
                "tag": "{{ai:summary}}",
                "type": "ai",
                "ai_tag": "summary"
            }
        ]
    }
    """
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    detected_tags = template.detected_tags or []

    # Processar tags para formato estruturado
    tags = []
    for tag_str in detected_tags:
        tag_info = {
            'tag': f'{{{{{tag_str}}}}}',
            'type': 'hubspot',
            'object_type': None,
            'property': None
        }

        # Verificar se é tag AI
        if tag_str.startswith('ai:'):
            tag_info['type'] = 'ai'
            tag_info['ai_tag'] = tag_str.replace('ai:', '')
        else:
            # Tentar extrair object_type e property
            parts = tag_str.split('.')
            if len(parts) >= 2:
                tag_info['object_type'] = parts[0]
                tag_info['property'] = '.'.join(parts[1:])
            else:
                tag_info['property'] = tag_str

        tags.append(tag_info)

    return jsonify({
        'tags': tags
    })
