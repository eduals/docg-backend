"""
Flow System Models - Workflow execution inspired by Activepieces
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from enum import Enum


class FlowStatus(str, Enum):
    """Flow status"""
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class FlowVersionState(str, Enum):
    """Flow version state"""
    DRAFT = "DRAFT"  # Being edited
    LOCKED = "LOCKED"  # Published, cannot be edited


class FlowRunStatus(str, Enum):
    """Flow run status"""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY = "READY"
    SENDING = "SENDING"
    SENT = "SENT"
    SIGNING = "SIGNING"
    SIGNED = "SIGNED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    PAUSED = "PAUSED"


class TriggerEventStatus(str, Enum):
    """Trigger event status"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Flow(db.Model):
    """
    Flow - Visual workflow definition
    Similar to Workflow but follows Activepieces architecture
    """
    __tablename__ = 'flow'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    name = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)

    # Ownership
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    folder_id = db.Column(UUID(as_uuid=True), db.ForeignKey('folder.id', ondelete='SET NULL'))

    # Status
    status = db.Column(db.String(50), default='DISABLED', nullable=False)  # ENABLED, DISABLED

    # Published version
    published_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow_version.id', ondelete='SET NULL'))

    # Schedule
    schedule = db.Column(JSONB)  # Cron or interval configuration

    # Relationships
    project = db.relationship('Project', back_populates='flows')
    folder = db.relationship('Folder', back_populates='flows')
    versions = db.relationship('FlowVersion', back_populates='flow', foreign_keys='FlowVersion.flow_id', cascade='all, delete-orphan')
    runs = db.relationship('FlowRun', back_populates='flow', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        db.Index('idx_flow_project_id', 'project_id'),
        db.Index('idx_flow_folder_id', 'folder_id'),
        db.Index('idx_flow_status', 'status'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'display_name': self.display_name,
            'project_id': str(self.project_id),
            'folder_id': str(self.folder_id) if self.folder_id else None,
            'status': self.status,
            'published_version_id': str(self.published_version_id) if self.published_version_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class FlowVersion(db.Model):
    """
    Flow Version - Versioned workflow definition
    Each flow can have multiple versions, but only one can be published
    """
    __tablename__ = 'flow_version'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ownership
    flow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow.id', ondelete='CASCADE'), nullable=False)

    # Version info
    display_name = db.Column(db.String(255), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)  # Incremental version

    # State
    state = db.Column(db.String(50), default='DRAFT', nullable=False)  # DRAFT, LOCKED

    # Trigger configuration
    trigger = db.Column(JSONB, nullable=False)  # Trigger step definition

    # Flow definition - Visual graph
    definition = db.Column(JSONB, nullable=False)  # Complete flow structure

    # Valid flag (for validation)
    is_valid = db.Column(db.Boolean, default=True)

    # Relationships
    flow = db.relationship('Flow', back_populates='versions', foreign_keys=[flow_id])

    # Indexes
    __table_args__ = (
        db.Index('idx_flow_version_flow_id', 'flow_id'),
        db.Index('idx_flow_version_state', 'state'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'flow_id': str(self.flow_id),
            'display_name': self.display_name,
            'version_number': self.version_number,
            'state': self.state,
            'trigger': self.trigger,
            'definition': self.definition,
            'is_valid': self.is_valid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class FlowRun(db.Model):
    """
    Flow Run - Execution instance of a flow
    Equivalent to WorkflowExecution but follows Activepieces model
    """
    __tablename__ = 'flow_run'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ownership
    flow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow.id', ondelete='CASCADE'), nullable=False)
    flow_version_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow_version.id', ondelete='SET NULL'))
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    # Execution state
    status = db.Column(db.String(50), default='QUEUED', nullable=False)
    progress = db.Column(db.Integer, default=0)  # 0-100

    # Timing
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)  # Duration in milliseconds

    # Current execution state
    current_step = db.Column(JSONB)  # {index, label, node_id, node_type}

    # Errors
    last_error_human = db.Column(db.Text)  # User-friendly error
    last_error_tech = db.Column(db.Text)  # Technical error with stack trace

    # Execution metadata
    trigger_output = db.Column(JSONB)  # Data from trigger
    steps_output = db.Column(JSONB)  # Output from each step

    # Preflight summary
    preflight_summary = db.Column(JSONB)  # {blocking_count, warning_count, groups: {...}}

    # Delivery and signature state
    delivery_state = db.Column(db.String(20))  # sending, sent, failed
    signature_state = db.Column(db.String(20))  # pending, signing, signed

    # Recommended actions
    recommended_actions = db.Column(JSONB)  # [{action, label, description, ...}]

    # Phase metrics
    phase_metrics = db.Column(JSONB)  # {phase: {started_at, completed_at, duration_ms}}

    # Correlation ID for distributed tracing
    correlation_id = db.Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)

    # Pause/Resume
    paused_at = db.Column(db.DateTime)
    pause_reason = db.Column(db.String(255))

    # Relationships
    flow = db.relationship('Flow', back_populates='runs')
    flow_version = db.relationship('FlowVersion')
    logs = db.relationship('FlowRunLog', back_populates='flow_run', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        db.Index('idx_flow_run_flow_id', 'flow_id'),
        db.Index('idx_flow_run_project_id', 'project_id'),
        db.Index('idx_flow_run_status', 'status'),
        db.Index('idx_flow_run_created_at', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'flow_id': str(self.flow_id),
            'flow_version_id': str(self.flow_version_id) if self.flow_version_id else None,
            'project_id': str(self.project_id),
            'status': self.status,
            'progress': self.progress,
            'current_step': self.current_step,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'duration_ms': self.duration_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class FlowRunLog(db.Model):
    """
    Flow Run Log - Structured logs for flow execution
    """
    __tablename__ = 'flow_run_log'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Ownership
    flow_run_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow_run.id', ondelete='CASCADE'), nullable=False)
    step_id = db.Column(UUID(as_uuid=True))  # Nullable - can be flow-level log

    # Log data
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    level = db.Column(db.String(20), nullable=False)  # ok, warn, error
    domain = db.Column(db.String(50), nullable=False)  # preflight, step, delivery, signature
    message_human = db.Column(db.Text, nullable=False)  # User-friendly message
    details_tech = db.Column(db.Text)  # Stack trace/technical details

    # Correlation
    correlation_id = db.Column(UUID(as_uuid=True), index=True)

    # Relationships
    flow_run = db.relationship('FlowRun', back_populates='logs')

    # Indexes
    __table_args__ = (
        db.Index('idx_flow_run_log_flow_run_id', 'flow_run_id'),
        db.Index('idx_flow_run_log_level', 'level'),
        db.Index('idx_flow_run_log_domain', 'domain'),
    )


class TriggerEvent(db.Model):
    """
    Trigger Event - Queue of trigger events to process
    """
    __tablename__ = 'trigger_event'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Source
    flow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('flow.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    # Trigger data
    source_name = db.Column(db.String(100), nullable=False)  # webhook, schedule, manual
    payload = db.Column(JSONB, nullable=False)  # Trigger payload data

    # Status
    status = db.Column(db.String(50), default='PENDING', nullable=False)  # PENDING, PROCESSING, SUCCESS, FAILED

    # Indexes
    __table_args__ = (
        db.Index('idx_trigger_event_flow_id', 'flow_id'),
        db.Index('idx_trigger_event_status', 'status'),
        db.Index('idx_trigger_event_created_at', 'created_at'),
    )
