from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
import os
from app.config import Config
from app.database import db, init_db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configurar CORS
    # Permitir origins do frontend (localhost para dev e produção)
    allowed_origins = [
        'http://localhost:5173',  # Vite dev server
        'http://localhost:3000',  # Alternativa
        'https://docg.pipehub.co',  # Produção
    ]
    
    # Adicionar origins de variável de ambiente se existir
    env_origins = os.getenv('CORS_ORIGINS', '')
    if env_origins:
        allowed_origins.extend([origin.strip() for origin in env_origins.split(',')])
    
    CORS(app,
         resources={r"/api/*": {"origins": allowed_origins}},
         supports_credentials=False,  # Não precisa de credentials com Bearer token
         allow_headers=["Content-Type", "Authorization", "X-Organization-ID", "X-User-Email"],
         methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    
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

    # Novos endpoints de executions (Features 2, 5, 6, 7, 10, 12)
    from app.controllers.api.v1.executions import bp as executions_bp
    app.register_blueprint(executions_bp)

    # Preflight endpoint (Feature 2)
    from app.controllers.api.v1.executions.preflight import preflight_bp
    app.register_blueprint(preflight_bp)

    from app.routes import templates
    app.register_blueprint(templates.templates_bp)
    
    from app.routes import connections
    app.register_blueprint(connections.connections_bp)
    
    from app.routes import organizations
    app.register_blueprint(organizations.organizations_bp)
    
    # Rotas de segurança (sessões, login history, 2FA, API keys) - registrar ANTES de users para evitar conflito
    try:
        from app.routes import security
        app.register_blueprint(security.security_bp)
        print(f"[DEBUG] Security blueprint registrado: {security.security_bp.name} com prefix {security.security_bp.url_prefix}")
    except Exception as e:
        print(f"[ERROR] Erro ao registrar security blueprint: {e}")
        import traceback
        traceback.print_exc()
    
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
    
    from app.routes import google_forms_routes
    app.register_blueprint(google_forms_routes.google_forms_bp)
    
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
    
    # Rotas de provedores de assinatura
    from app.routes import signature_providers
    app.register_blueprint(signature_providers.signature_providers_bp)
    
    # Rotas de assinaturas
    from app.routes import signatures
    app.register_blueprint(signatures.signatures_bp)
    
    # Rotas do HubSpot
    from app.routes import hubspot_oauth_routes
    app.register_blueprint(hubspot_oauth_routes.hubspot_oauth_bp)
    
    from app.routes import hubspot_events
    app.register_blueprint(hubspot_events.hubspot_events_bp)
    
    from app.routes import hubspot_workflow_action
    app.register_blueprint(hubspot_workflow_action.hubspot_workflow_bp)
    
    from app.routes import hubspot_properties
    app.register_blueprint(hubspot_properties.hubspot_properties_bp)
    
    # Rotas de webhooks
    from app.routes import webhooks
    app.register_blueprint(webhooks.webhooks_bp)
    
    # Rotas de checkout (Stripe)
    from app.routes import checkout
    app.register_blueprint(checkout.checkout_bp)
    
    # Rotas de billing (Stripe)
    from app.routes import billing
    app.register_blueprint(billing.billing_bp)
    
    # Rotas de Microsoft OAuth
    from app.routes import microsoft_oauth_routes
    app.register_blueprint(microsoft_oauth_routes.microsoft_oauth_bp)
    
    # Rotas de Microsoft (OneDrive/SharePoint)
    from app.routes import microsoft_routes
    app.register_blueprint(microsoft_routes.microsoft_bp)
    
    # Rotas de aprovações
    from app.routes import approvals
    app.register_blueprint(approvals.approvals_bp)
    
    # Rotas de mapeamentos globais
    from app.routes import global_field_mappings
    app.register_blueprint(global_field_mappings.global_field_mappings_bp)

    # SSE (Server-Sent Events) para real-time
    from app.routes import sse
    app.register_blueprint(sse.sse_bp)

    return app

