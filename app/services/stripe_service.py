"""
Serviço para integração com Stripe
Gerencia configuração de planos e funções auxiliares
"""
import stripe
from app.config import Config

# Configurar Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY

# Configuração de planos
PLAN_CONFIG = {
    'starter': {
        'product_id': 'prod_Tb764p2NUbTPwe',
        'price_id': 'price_1SduroHBxNwn6RMGjXIgE6xu',  # Encontrado
        'users_limit': 3,
        'documents_limit': 50,
        'workflows_limit': 5,
    },
    'pro': {
        'product_id': 'prod_Tb76AgLObhBSYI',
        'price_id': 'price_XXXXX',  # A ser preenchido - buscar no Stripe Dashboard
        'users_limit': 10,
        'documents_limit': 200,
        'workflows_limit': 20,
    },
    'team': {
        'product_id': 'prod_Tb76QNv3dFnpUP',
        'price_id': 'price_XXXXX',  # A ser preenchido - buscar no Stripe Dashboard
        'users_limit': None,  # ilimitado
        'documents_limit': 500,
        'workflows_limit': 50,
    },
    'enterprise': {
        'product_id': 'prod_Tb76hPi1RaG40D',
        'price_id': 'price_1SduscHBxNwn6RMG0ZmX5OJr',  # Já encontrado
        'users_limit': None,  # ilimitado
        'documents_limit': None,  # ilimitado
        'workflows_limit': None,  # ilimitado
    }
}


def get_plan_config(plan_name):
    """Retorna configuração de um plano"""
    return PLAN_CONFIG.get(plan_name)


def get_price_id(plan_name):
    """Retorna price_id de um plano"""
    config = get_plan_config(plan_name)
    return config.get('price_id') if config else None


def create_or_get_customer(organization, email, name=None):
    """
    Cria ou busca um Customer no Stripe
    
    Args:
        organization: Instância de Organization
        email: Email do cliente
        name: Nome do cliente (opcional)
    
    Returns:
        customer_id (str): ID do customer no Stripe
    """
    # Se já tem customer_id, buscar para verificar se ainda existe
    if organization.stripe_customer_id:
        try:
            customer = stripe.Customer.retrieve(organization.stripe_customer_id)
            return customer.id
        except stripe.error.InvalidRequestError:
            # Customer não existe mais, criar novo
            pass
    
    # Criar novo customer
    customer_data = {
        'email': email,
        'metadata': {
            'organization_id': str(organization.id),
            'organization_name': organization.name,
        }
    }
    
    if name:
        customer_data['name'] = name
    
    customer = stripe.Customer.create(**customer_data)
    return customer.id


def create_checkout_session(customer_id, price_id, organization_id, plan_name, is_onboarding=False):
    """
    Cria uma Checkout Session no Stripe
    
    Args:
        customer_id: ID do customer no Stripe
        price_id: ID do price no Stripe
        organization_id: UUID da organização
        plan_name: Nome do plano (starter, pro, team, enterprise)
        is_onboarding: Se está no fluxo de onboarding
    
    Returns:
        checkout_session: Objeto da sessão do Stripe
    """
    frontend_url = Config.FRONTEND_URL
    
    success_url = f"{frontend_url}/onboarding?step=6&session_id={{CHECKOUT_SESSION_ID}}"
    if not is_onboarding:
        success_url = f"{frontend_url}/dashboard?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    
    cancel_url = f"{frontend_url}/onboarding?step=5&canceled=true"
    if not is_onboarding:
        cancel_url = f"{frontend_url}/pricing?canceled=true"
    
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=[{
            'price': price_id,
            'quantity': 1,
        }],
        mode='subscription',
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'organization_id': str(organization_id),
            'plan': plan_name,
            'onboarding': str(is_onboarding).lower(),
        },
        allow_promotion_codes=True,
    )
    
    return session
