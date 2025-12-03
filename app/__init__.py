from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from app.config import Config
from app.database import db, init_db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Inicializar CORS
    CORS(app)
    
    # Inicializar banco de dados
    db.init_app(app)
    
    # Inicializar Flask-Migrate
    migrate = Migrate(app, db)
    
    init_db(app)
    
    # Registrar rotas novas (DocGen)
    from app.routes import documents
    app.register_blueprint(documents.documents_bp)
    
    from app.routes import workflows
    app.register_blueprint(workflows.workflows_bp)
    
    from app.routes import templates
    app.register_blueprint(templates.templates_bp)
    
    from app.routes import connections
    app.register_blueprint(connections.connections_bp)
    
    from app.routes import organizations
    app.register_blueprint(organizations.organizations_bp)
    
    from app.routes import users
    app.register_blueprint(users.users_bp)
    
    from app.routes import features
    app.register_blueprint(features.features_bp)
    
    # Health check endpoint
    from app.routes import health
    app.register_blueprint(health.bp)
    
    # Registrar rotas legadas (compatibilidade)
    # account_routes removido - migrado para organizations
    from app.routes import field_mappings_routes
    app.register_blueprint(field_mappings_routes.bp)
    
    from app.routes import envelope_routes
    app.register_blueprint(envelope_routes.bp)
    
    from app.routes import google_oauth_routes
    app.register_blueprint(google_oauth_routes.bp)
    
    from app.routes import google_drive_routes
    app.register_blueprint(google_drive_routes.bp)
    
    from app.routes import settings
    app.register_blueprint(settings.settings_bp)
    
    # Rota RISC (Cross-Account Protection)
    from app.routes import risc_routes
    app.register_blueprint(risc_routes.bp)
    
    # Rotas legadas de templates - usar nome diferente
    from app.routes import templates_routes
    app.register_blueprint(templates_routes.bp, name='legacy_templates')
    
    # Rotas de IA (providers, models)
    from app.routes import ai_routes
    app.register_blueprint(ai_routes.ai_bp)
    
    # Rotas do HubSpot
    from app.routes import hubspot_oauth_routes
    app.register_blueprint(hubspot_oauth_routes.hubspot_oauth_bp)
    
    from app.routes import hubspot_events
    app.register_blueprint(hubspot_events.hubspot_events_bp)
    
    from app.routes import hubspot_workflow_action
    app.register_blueprint(hubspot_workflow_action.hubspot_workflow_bp)
    
    return app

