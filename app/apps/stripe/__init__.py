"""Stripe App - Integração com Stripe para pagamentos."""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class StripeApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Stripe'

    @property
    def key(self) -> str:
        return 'stripe'

    @property
    def icon_url(self) -> str:
        return 'https://stripe.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'Payment processing with Stripe'

    @property
    def base_url(self) -> str:
        return 'https://api.stripe.com/v1'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(auth_type=AuthType.BEARER)

    def _setup(self):
        from .actions import create_checkout, manage_subscription
        self.register_action(ActionDefinition(key='create-checkout', name='Create Checkout', description='Creates a Stripe checkout session', handler=create_checkout.run))
        self.register_action(ActionDefinition(key='manage-subscription', name='Manage Subscription', description='Manages customer subscriptions', handler=manage_subscription.run))


stripe_app = StripeApp()
