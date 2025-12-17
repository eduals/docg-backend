import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

# Node type constants
TRIGGER_NODE_TYPES = ['hubspot', 'webhook', 'google-forms', 'trigger']  # 'trigger' para compatibilidade

class Workflow(db.Model):
    __tablename__ = 'workflows'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='draft')  # draft, active, paused, archived
    
    # Source
    source_connection_id = db.Column(UUID(as_uuid=True), db.ForeignKey('data_source_connections.id'))
    source_object_type = db.Column(db.String(100))
    source_config = db.Column(JSONB)
    
    # Template
    template_id = db.Column(UUID(as_uuid=True), db.ForeignKey('templates.id'))
    
    # Output
    output_folder_id = db.Column(db.String(255))
    output_name_template = db.Column(db.String(500))
    create_pdf = db.Column(db.Boolean, default=True)
    
    # Trigger
    trigger_type = db.Column(db.String(50), default='manual')
    trigger_config = db.Column(JSONB)
    
    # Post Actions
    post_actions = db.Column(JSONB)
    
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    field_mappings = db.relationship('WorkflowFieldMapping', backref='workflow', lazy='dynamic', cascade='all, delete-orphan')
    ai_mappings = db.relationship('AIGenerationMapping', backref='workflow', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('GeneratedDocument', backref='workflow', lazy='dynamic')
    executions = db.relationship('WorkflowExecution', backref='workflow', lazy='dynamic')
    
    def to_dict(self, include_mappings=False, include_ai_mappings=False):
        result = {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'source_connection_id': str(self.source_connection_id) if self.source_connection_id else None,
            'source_object_type': self.source_object_type,
            'source_config': self.source_config,
            'template_id': str(self.template_id) if self.template_id else None,
            'output_folder_id': self.output_folder_id,
            'output_name_template': self.output_name_template,
            'create_pdf': self.create_pdf,
            'trigger_type': self.trigger_type,
            'trigger_config': self.trigger_config,
            'post_actions': self.post_actions,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_mappings:
            result['field_mappings'] = [
                m.to_dict() for m in self.field_mappings
            ]
        
        if include_ai_mappings:
            result['ai_mappings'] = [
                m.to_dict() for m in self.ai_mappings
            ]
        
        if self.template:
            result['template'] = {
                'id': str(self.template.id),
                'name': self.template.name,
                'google_file_type': self.template.google_file_type,
                'thumbnail_url': self.template.thumbnail_url
            }
        
        return result


class WorkflowFieldMapping(db.Model):
    __tablename__ = 'workflow_field_mappings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False)
    template_tag = db.Column(db.String(255), nullable=False)
    source_field = db.Column(db.String(255), nullable=False)
    transform_type = db.Column(db.String(50))
    transform_config = db.Column(JSONB)
    default_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'template_tag', name='unique_workflow_tag'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'workflow_id': str(self.workflow_id),
            'template_tag': self.template_tag,
            'source_field': self.source_field,
            'transform_type': self.transform_type,
            'transform_config': self.transform_config,
            'default_value': self.default_value,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AIGenerationMapping(db.Model):
    """
    Mapeamento de tags AI para geração de texto via LLM.
    
    Tags no formato {{ai:nome_da_tag}} são processadas usando este mapeamento
    para gerar texto dinamicamente via provedores de IA (OpenAI, Gemini, etc).
    """
    __tablename__ = 'ai_generation_mappings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False)
    
    # Tag e configuração
    ai_tag = db.Column(db.String(255), nullable=False)  # Ex: "paragrapho1"
    source_fields = db.Column(JSONB)  # Array de campos HubSpot para usar no prompt
    
    # Provedor e modelo
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'gemini', 'anthropic'
    model = db.Column(db.String(100), nullable=False)    # 'gpt-4', 'gemini-1.5-pro', etc
    ai_connection_id = db.Column(UUID(as_uuid=True), db.ForeignKey('data_source_connections.id', ondelete='SET NULL'))
    
    # Configuração do prompt
    prompt_template = db.Column(db.Text)  # Template com placeholders {{field}}
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer, default=1000)
    
    # Fallback (se IA falhar)
    fallback_value = db.Column(db.Text)  # Valor padrão se geração falhar
    
    # Métricas de uso (para auditoria/debugging)
    last_used_at = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'ai_tag', name='unique_workflow_ai_tag'),
        db.Index('idx_ai_mapping_connection', 'ai_connection_id'),
    )
    
    # Relationships
    ai_connection = db.relationship('DataSourceConnection', foreign_keys=[ai_connection_id])
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'workflow_id': str(self.workflow_id),
            'ai_tag': self.ai_tag,
            'source_fields': self.source_fields,
            'provider': self.provider,
            'model': self.model,
            'ai_connection_id': str(self.ai_connection_id) if self.ai_connection_id else None,
            'prompt_template': self.prompt_template,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'fallback_value': self.fallback_value,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def increment_usage(self):
        """Incrementa contador de uso e atualiza timestamp"""
        self.usage_count = (self.usage_count or 0) + 1
        self.last_used_at = datetime.utcnow()


class WorkflowNode(db.Model):
    """
    Node de um workflow. Representa um passo na execução do workflow.
    
    Tipos de nodes:
    - hubspot, webhook, google-forms: Fonte de dados (sempre o primeiro, position = 1)
    - google-docs: Geração de documento no Google Docs
    - review-documents: Aprovação humana
    - request-signatures: Envio para assinatura
    - webhook: Chamada de webhook externo
    """
    __tablename__ = 'workflow_nodes'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False)
    
    # Tipo do node
    node_type = db.Column(db.String(50), nullable=False)  
    # Valores: 'trigger', 'google-docs', 'clicksign', 'webhook', etc.
    
    # Posição e ordem
    position = db.Column(db.Integer, nullable=False)  # Ordem no workflow (1 = primeiro)
    parent_node_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_nodes.id', ondelete='SET NULL'))
    
    # Configuração específica do node (JSONB)
    config = db.Column(JSONB)
    # Para trigger: { trigger_type, source_connection_id, source_object_type, trigger_config }
    # Para google-docs: { template_id, output_name_template, output_folder_id, create_pdf, remove_branding, field_mappings }
    # Para clicksign: { connection_id, recipients, document_source, document_id }
    # Para webhook: { url, method, headers, body_template }
    
    # Webhook token (para triggers webhook)
    webhook_token = db.Column(db.String(255), unique=True, nullable=True)
    
    # Status
    status = db.Column(db.String(50), default='draft')  # draft, configured, active
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow = db.relationship('Workflow', backref='nodes', foreign_keys=[workflow_id])
    parent = db.relationship('WorkflowNode', remote_side=[id], backref='children')
    
    # Índices
    __table_args__ = (
        db.Index('idx_workflow_node_workflow', 'workflow_id'),
        db.Index('idx_workflow_node_position', 'workflow_id', 'position'),
        db.UniqueConstraint('workflow_id', 'position', name='unique_workflow_position'),
    )
    
    def to_dict(self, include_config=False):
        """Converte node para dicionário"""
        result = {
            'id': str(self.id),
            'workflow_id': str(self.workflow_id),
            'node_type': self.node_type,
            'position': self.position,
            'parent_node_id': str(self.parent_node_id) if self.parent_node_id else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_config:
            result['config'] = self.config or {}
        
        return result
    
    def is_trigger(self):
        """Verifica se é um node trigger (sempre position 1)"""
        return self.node_type in TRIGGER_NODE_TYPES
    
    def is_step(self):
        """Verifica se é um node step (position > 1)"""
        return not self.is_trigger()
    
    def generate_webhook_token(self):
        """Gera token único para webhook trigger"""
        import secrets
        self.webhook_token = secrets.token_urlsafe(32)
        return self.webhook_token
    
    def is_configured(self):
        """Verifica se o node está configurado"""
        if self.status == 'configured':
            return True
        
        # Validação básica por tipo
        if not self.config:
            return False
        
        if self.node_type in TRIGGER_NODE_TYPES:
            if self.node_type == 'webhook' or (self.node_type == 'trigger' and self.config.get('trigger_type') == 'webhook'):
                return bool(self.webhook_token and self.config.get('field_mapping'))
            elif self.node_type == 'google-forms' or (self.node_type == 'trigger' and self.config.get('source_type') == 'google-forms'):
                return bool(self.config.get('form_id'))
            else:  # hubspot ou trigger com trigger_type='hubspot'
                return bool(self.config.get('source_connection_id') and self.config.get('source_object_type'))
        elif self.node_type == 'google-docs':
            return bool(self.config.get('template_id'))
        elif self.node_type == 'google-slides':
            return bool(self.config.get('template_id'))
        elif self.node_type == 'microsoft-word':
            return bool(self.config.get('template_id') and self.config.get('connection_id'))
        elif self.node_type == 'microsoft-powerpoint':
            return bool(self.config.get('template_id') and self.config.get('connection_id'))
        elif self.node_type == 'gmail':
            return bool(self.config.get('connection_id') and self.config.get('to') and self.config.get('subject_template'))
        elif self.node_type == 'outlook':
            return bool(self.config.get('connection_id') and self.config.get('to') and self.config.get('subject_template'))
        elif self.node_type == 'review-documents':
            return bool(self.config.get('approver_emails'))
        elif self.node_type == 'request-signatures':
            return bool(self.config.get('connection_id') and self.config.get('recipients'))
        # Compatibilidade com nomes antigos
        elif self.node_type == 'human-in-loop':
            return bool(self.config.get('approver_emails'))
        elif self.node_type == 'clicksign':
            return bool(self.config.get('connection_id') and self.config.get('recipients'))
        # NOTA: webhook node externo será tratado depois - por enquanto apenas trigger webhook
        
        return False

