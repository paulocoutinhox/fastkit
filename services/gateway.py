"""The payment providers selected by an integration, built from their shared contract."""

from enums.provider import Provider
from services.payment_provider import PaymentProvider
from services.revenue_cat_provider import RevenueCatProvider
from services.stripe_provider import StripeProvider

PROVIDERS: dict[Provider, PaymentProvider] = {Provider.REVENUECAT: RevenueCatProvider(), Provider.STRIPE: StripeProvider()}
