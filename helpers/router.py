"""The order every router is registered in, which is what keeps a literal path from being swallowed."""

from fastapi import APIRouter, FastAPI

from helpers.crud import RESOURCES
from helpers.settings import settings
from routes import account, auth, banner, commerce, contact, content, country, credit, currency, email, event, gallery, integration, language, meta, newsletter, subscription, system_log, tenant, upload, user, webhook
from routes.site import account as site_account
from routes.site import checkout as site_checkout
from routes.site import pages as site_pages
from routes.site import seo as site_seo

# The specific paths of a module come before its crud router, so a literal segment is never swallowed by the record id route.
ROUTERS: tuple[APIRouter, ...] = (
    meta.router,
    auth.router,
    webhook.router,
    account.router,
    commerce.account_router,
    upload.router,
    language.public_router,
    country.public_router,
    newsletter.public_router,
    contact.router,
    content.public_router,
    banner.public_router,
    gallery.public_router,
    commerce.public_router,
    event.public_router,
    subscription.public_router,
    subscription.account_router,
    subscription.activation_router,
    tenant.router,
    language.router,
    country.router,
    user.router,
    user.address_router,
    content.router,
    content.category_router,
    banner.router,
    gallery.router,
    gallery.photo_router,
    commerce.router,
    commerce.purchase_router,
    commerce.user_product_router,
    subscription.plan_router,
    subscription.entitlement_router,
    subscription.plan_entitlement_router,
    subscription.benefit_router,
    subscription.router,
    subscription.user_entitlement_router,
    subscription.subscription_benefit_router,
    subscription.benefit_grant_router,
    integration.router,
    integration.external_product_router,
    integration.webhook_event_router,
    event.router,
    email.router,
    newsletter.router,
    system_log.router,
    credit.write_router,
    credit.router,
    currency.router,
    currency.balance_router,
)


RESOURCES.update(router.served for router in ROUTERS if hasattr(router, "served"))


# The site takes the root, so its literal paths are registered before the ones that carry a language segment.
SITE_ROUTERS: tuple[APIRouter, ...] = (site_seo.router, site_account.router, site_checkout.router, site_pages.router)


def setup(app: FastAPI):
    for router in ROUTERS:
        app.include_router(router, prefix=settings.api_path)


def setup_site(app: FastAPI):
    for router in SITE_ROUTERS:
        app.include_router(router)
