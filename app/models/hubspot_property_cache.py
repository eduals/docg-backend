import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class HubSpotPropertyCache(db.Model):
    """
    Cache de propriedades do HubSpot para melhorar performance.
    """
    __tablename__ = 'hubspot_property_cache'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    
    object_type = db.Column(db.String(50), nullable=False)  # deal, contact, company, ticket
    property_name = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(255))
    type = db.Column(db.String(50))  # string, number, date, enum, etc.
    options = db.Column(JSONB)  # Para campos de seleção/enum
    
    # Cache metadata
    cached_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'object_type', 'property_name', name='unique_org_object_property'),
        db.Index('idx_property_cache_org_object', 'organization_id', 'object_type'),
    )
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'name': self.property_name,
            'label': self.label or self.property_name,
            'type': self.type,
            'options': self.options,
            'tag': f'{{{{{".".join([self.object_type, self.property_name])}}}}}'
        }
