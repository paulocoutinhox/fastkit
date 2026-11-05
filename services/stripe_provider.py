import hashlib
import hmac
from datetime import datetime
from decimal import Decimal

import httpx2

from enums.environment import Environment
from enums.normalized_action import NormalizedAction
from enums.purchase_status import PurchaseStatus
from enums.subscription_status import SubscriptionStatus
from helpers.authentication_error import AuthenticationError
from helpers.money import from_minor_units
from models.integration import Integration
from services.credential import Credential
from services.inbound_call import InboundCall
from services.payment_provider import PaymentProvider
from services.provider_event import ProviderEvent
from services.provider_purchase import ProviderPurchase
from services.revenue_cat_provider import API_KEY, WEBHOOK_SECRET, epoch_of, fresh, matches, signature_parts


class StripeProvider(PaymentProvider):
    """Stripe signs what it posts and its notice carries the object, so the state is read from the event and never asked for."""

    API = "https://api.stripe.com/v1"
    SIGNATURE_HEADER = "stripe-signature"
    event_stated = True

    credentials = (Credential("stripe_api_key", "Secret key", "Developers -> API keys.", API_KEY), Credential("stripe_webhook_secret", "Signing secret", "Developers -> Webhooks -> the endpoint -> Signing secret.", WEBHOOK_SECRET))

    # What a notice was about, for the record and the grid, where an update is only nameable when the object says which kind it was.
    ACTIONS = {
        "customer.subscription.created": NormalizedAction.ACTIVATE,
        "customer.subscription.deleted": NormalizedAction.EXPIRE,
        "customer.subscription.paused": NormalizedAction.SUSPEND,
        "customer.subscription.resumed": NormalizedAction.RESUME,
        "invoice.paid": NormalizedAction.RENEW,
        "invoice.payment_failed": NormalizedAction.ENTER_GRACE,
        "charge.refunded": NormalizedAction.REFUND,
        "checkout.session.completed": NormalizedAction.ACTIVATE,
    }

    STATUSES = {
        "trialing": SubscriptionStatus.TRIALING,
        "active": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.GRACE_PERIOD,
        "unpaid": SubscriptionStatus.GRACE_PERIOD,
        "paused": SubscriptionStatus.SUSPENDED,
        "incomplete": SubscriptionStatus.PENDING,
        "incomplete_expired": SubscriptionStatus.EXPIRED,
        "canceled": SubscriptionStatus.EXPIRED,
    }

    # An invoice says what was paid and what was asked for in two fields, and a failed one paid nothing.
    # Where a notice writes the amount it is about: what an invoice took or failed to take, and what a charge gave back.
    AMOUNTS = {"invoice.paid": "amount_paid", "invoice.payment_failed": "amount_due", "charge.refunded": "amount_refunded"}

    # Where every other object writes it: what a session charged and what a dispute argues over.
    OBJECT_AMOUNTS = {"checkout.session": "amount_total", "dispute": "amount"}

    PAYMENTS = {"paid": PurchaseStatus.PAID, "unpaid": PurchaseStatus.PENDING, "no_payment_required": PurchaseStatus.PAID}

    # A boleto or a debit leaves the session unpaid for days, and how it ended arrives as an event of its own.
    SESSION_OUTCOMES = {"checkout.session.async_payment_succeeded": PurchaseStatus.PAID, "checkout.session.async_payment_failed": PurchaseStatus.FAILED, "checkout.session.expired": PurchaseStatus.CANCELED}

    # A dispute moves the payment only once it settled: lost is the money gone, won is the money kept, and everything else is a dispute still being argued.
    DISPUTES = {"lost": PurchaseStatus.CHARGED_BACK, "won": PurchaseStatus.PAID}

    def authenticate(self, integration: Integration, call: InboundCall, secret: str) -> None:
        """The body of a notice here is the state itself, so a call nobody can verify is refused rather than believed: without a secret, whoever knew the address could mark a purchase paid."""
        if not secret:
            raise AuthenticationError("error.webhook-signature-invalid")

        header = call.header(self.SIGNATURE_HEADER)

        if not header:
            raise AuthenticationError("error.webhook-signature-invalid")

        self.verify(secret, header, call)

    def verify(self, secret: str, header: str, call: InboundCall) -> None:
        """HMAC-SHA256 over `<t>.<raw body>`, and the body has to be the bytes that arrived because reserializing changes them."""
        moment, signatures = signature_parts(header)

        if not moment or not signatures:
            raise AuthenticationError("error.webhook-signature-invalid")

        if not fresh(moment):
            raise AuthenticationError("error.webhook-signature-invalid")

        expected = hmac.new(secret.encode(), f"{moment}.".encode() + call.body, hashlib.sha256).hexdigest()

        if not any(matches(given, expected) for given in signatures):
            raise AuthenticationError("error.webhook-signature-invalid")

    async def read(self, integration: Integration, call: InboundCall, client: httpx2.AsyncClient) -> ProviderEvent | None:
        envelope = call.data()

        if envelope.get("object") != "event" or not isinstance(envelope.get("data"), dict):
            return None

        entry = envelope["data"].get("object") or {}
        event_type = str(envelope.get("type") or "")
        subscription = entry.get("object") == "subscription"

        return ProviderEvent(
            external_event_id=str(envelope.get("id") or ""),
            event_type=event_type,
            account_token=self.text(self.metadata_of(entry).get("account_token")),
            product_reference=self.reference_of(entry),
            action=self.action(event_type, entry),
            state=(self.purchase_of(entry),) if subscription else None,
            reference=self.text(entry.get("client_reference_id")),
            purchase_status=self.payment_of(event_type, entry),
            payment_id=self.text(entry.get("payment_intent")),
            amount=self.money(self.amount_of(event_type, entry), self.text(entry.get("currency"))),
            currency=(self.text(entry.get("currency")) or "").upper() or None,
            occurred_at=self.moment(envelope.get("created")),
        )

    def amount_of(self, event_type: str, entry: dict):
        field = self.AMOUNTS.get(event_type) or self.OBJECT_AMOUNTS.get(entry.get("object"))

        return None if field is None else entry.get(field)

    def action(self, event_type: str, entry: dict) -> NormalizedAction | None:
        """Names what the notice was about, reading the object itself when the event is an update, which is what most of a subscription's life arrives as."""
        if event_type != "customer.subscription.updated":
            return self.ACTIONS.get(event_type)

        if entry.get("pause_collection"):
            return NormalizedAction.SUSPEND

        if entry.get("cancel_at_period_end"):
            return NormalizedAction.CANCEL_AT_PERIOD_END

        return None

    def payment_of(self, event_type: str, entry: dict) -> PurchaseStatus | None:
        """Answers what became of a payment this side opened, which a checkout session, a charge that went back and a dispute that settled are the things to say anything about."""
        if entry.get("object") == "dispute":
            return self.DISPUTES.get(str(entry.get("status") or ""))

        if entry.get("object") == "charge":
            # Stripe raises `refunded` only where the whole charge went back, so a partial one leaves the purchase where it stands.
            return PurchaseStatus.REFUNDED if entry.get("refunded") else None

        if entry.get("object") != "checkout.session" or entry.get("mode") != "payment":
            return None

        if event_type in self.SESSION_OUTCOMES:
            return self.SESSION_OUTCOMES[event_type]

        return self.PAYMENTS.get(str(entry.get("payment_status") or ""))

    def first_item(self, entry: dict) -> dict:
        """Answers the first item of the subscription, which is where Stripe moved the current period to."""
        items = (entry.get("items") or {}).get("data") or []

        return items[0] if items else {}

    def price_of(self, entry: dict) -> str | None:
        return self.text(((self.first_item(entry).get("price") or {}).get("id")))

    def metadata_of(self, entry: dict) -> dict:
        """An invoice carries no metadata of its own, and the subscription that generated it is copied onto it when it is finalized."""
        if entry.get("object") == "invoice":
            return ((entry.get("parent") or {}).get("subscription_details") or {}).get("metadata") or {}

        return entry.get("metadata") or {}

    def reference_of(self, entry: dict) -> str | None:
        """The price a subscription or its invoice was for, which is what an external product is mapped by."""
        if entry.get("object") == "subscription":
            return self.price_of(entry)

        if entry.get("object") == "invoice":
            return self.invoiced_price(entry)

        return None

    def invoiced_price(self, entry: dict) -> str | None:
        """Prorations come first in the lines of an invoice, so the price is read from the line the subscription item itself generated."""
        for line in (entry.get("lines") or {}).get("data") or []:
            details = (line.get("parent") or {}).get("subscription_item_details") or {}

            if details and not details.get("proration"):
                return self.text(((line.get("pricing") or {}).get("price_details") or {}).get("price"))

        return None

    def purchase_of(self, entry: dict) -> ProviderPurchase:
        item = self.first_item(entry)
        status = str(entry.get("status") or "")

        return ProviderPurchase(
            external_id=str(entry.get("id") or ""),
            product_reference=self.price_of(entry) or "",
            store="stripe",
            period_type=status or None,
            trial=status == "trialing",
            purchased_at=self.moment(item.get("current_period_start")),
            first_purchased_at=self.moment(entry.get("start_date")),
            period_ends_at=self.moment(item.get("current_period_end")),
            # A collection paused with no date to resume on is paused for as long as somebody leaves it, which is still a pause.
            paused=bool(entry.get("pause_collection")),
            unsubscribed_at=self.moment(entry.get("canceled_at")) if entry.get("cancel_at_period_end") else None,
            environment=Environment.PRODUCTION if entry.get("livemode") else Environment.SANDBOX,
            status=self.STATUSES.get(status),
        )

    def moment(self, value) -> datetime | None:
        """Reads a moment Stripe counted in whole seconds since the epoch."""
        return epoch_of(value, 1)

    def text(self, value) -> str | None:
        return str(value) if value not in (None, "") else None

    def money(self, amount, currency: str | None) -> Decimal | None:
        if amount is None or currency is None:
            return None

        return from_minor_units(amount, currency)
