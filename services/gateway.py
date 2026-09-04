"""The contract a payment gateway is written against, which knows nothing of the services that call it."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qsl, quote

import httpx

from enums.commerce import PurchaseStatus
from enums.integration import Environment, NormalizedAction, Provider
from enums.subscription import SubscriptionStatus
from helpers import remote
from helpers.dates import now
from helpers.errors import AuthenticationError
from helpers.money import from_minor_units
from models.integration import Integration

# How long a gateway is given to answer a question about one account.
SUBSCRIBER_TIMEOUT = 10.0

# What RevenueCat calls a period the buyer is not paying full price for, which is a trial in our terms.
TRIAL_PERIODS = ("TRIAL", "INTRO")

# What proves the caller is the provider is worth reading once and never keeping, so it is not written down with the rest.
SECRET_HEADERS = ("authorization", "cookie", "proxy-authorization")

# A gateway that asks for a pause without saying how long still gets one, and one that asks for an hour does not hold a whole pass.
DEFAULT_BACKOFF, MAX_BACKOFF = 1.0, 60.0

# Both gateways sign each delivery afresh, retries included, so a stamp older than this is a replay of a call that was legitimate once.
TOLERANCE = timedelta(minutes=5)


def matches(given: str, expected: str) -> bool:
    """The bytes are compared and never the text, because `compare_digest` refuses a string a caller filled with anything but ascii."""
    return hmac.compare_digest(given.encode(), expected.encode())


def fresh(moment: str) -> bool:
    """Whether the stamp inside a signature is of now, which is what tells a delivery from a call somebody kept."""
    try:
        stamped = datetime.fromtimestamp(int(moment), tz=timezone.utc)
    except (TypeError, ValueError):
        return False

    return abs(now() - stamped) <= TOLERANCE


def epoch_of(value, per_second: int) -> datetime | None:
    """A stamp nothing can read is a stamp the notice did not carry, and dropping the whole event over it loses what did arrive."""
    if not value:
        return None

    try:
        return datetime.fromtimestamp(int(value) / per_second, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def signature_parts(header: str) -> tuple[str | None, list[str]]:
    """Reads the `t=<unix>,v1=<hex>` header both gateways sign with, where v1 may repeat while a secret is being rolled, so every one of them is a candidate."""
    moment = None
    signatures = []

    for piece in header.split(","):
        if "=" not in piece:
            continue

        scheme, value = piece.split("=", 1)

        if scheme.strip() == "t":
            moment = value.strip()
        elif scheme.strip() == "v1":
            signatures.append(value.strip())

    return moment, signatures


class RateLimited(Exception):
    """The provider asked for a pause, and it says in the answer how long it wants."""

    def __init__(self, seconds: float):
        super().__init__(f"rate limited for {seconds}s")

        self.seconds = seconds


@dataclass(frozen=True)
class InboundCall:
    """What arrived, exactly as it arrived: the provider decides the method, the format and the headers, and we decide nothing."""

    method: str
    headers: dict = field(default_factory=dict)
    query: dict = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def data(self) -> dict:
        content_type = (self.header("content-type") or "").split(";")[0].strip()

        if content_type == "application/x-www-form-urlencoded":
            return dict(parse_qsl(self.text()))

        try:
            parsed = json.loads(self.text())
        except ValueError:
            return {}

        return parsed if isinstance(parsed, dict) else {}

    def is_empty(self) -> bool:
        return not self.body and not self.query

    def recorded(self) -> dict:
        return {"method": self.method, "query": self.query, "headers": {name: value for name, value in self.headers.items() if name not in SECRET_HEADERS}}


@dataclass(frozen=True)
class ProviderPurchase:
    """One line of what a provider says an account holds right now, recurring or bought once."""

    external_id: str
    product_reference: str
    store: str | None = None
    ownership: str | None = None
    period_type: str | None = None
    trial: bool = False
    purchased_at: datetime | None = None
    first_purchased_at: datetime | None = None
    period_ends_at: datetime | None = None
    grace_ends_at: datetime | None = None
    auto_resume_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    refunded_at: datetime | None = None
    environment: Environment = Environment.PRODUCTION
    recurring: bool = True

    # What the gateway calls this state, for the ones that name it instead of leaving it to be read off the dates.
    status: SubscriptionStatus | None = None


@dataclass(frozen=True)
class ProviderEvent:
    """An event says which account to look at and what it was about, and never what the state became."""

    external_event_id: str
    event_type: str
    account_token: str | None = None
    product_reference: str | None = None
    action: NormalizedAction | None = None

    # What this notice resolved the account to hold, where nothing at all means the notice said nothing about that.
    state: tuple[ProviderPurchase, ...] | None = None

    # The reference this side minted before sending the buyer away, echoed back by the gateway, and what the gateway calls the payment it settled.
    reference: str | None = None
    purchase_status: PurchaseStatus | None = None
    payment_id: str | None = None

    amount: Decimal | None = None
    currency: str | None = None
    occurred_at: datetime | None = None


# The key that reads the gateway, and the value that proves a call came from it.
API_KEY, WEBHOOK_SECRET = "api_key", "webhook_secret"


@dataclass(frozen=True)
class Credential:
    """A secret this gateway needs, under the name its own panel gives it and in a column named after the gateway."""

    field: str
    label: str
    hint: str
    role: str | None = None


class PaymentProvider:
    """A gateway authenticates its call and reads it, and says what an account holds by whichever of the two ways it has."""

    # The gateway answers what an account holds right now, which is the reliable source and the one a safety net can use.
    queryable = False

    # The gateway only tells, and its own notice carries enough to say what the account holds.
    event_stated = False

    # What an operator has to paste, named the way the gateway names it, because a generic label sends them looking for a field that is not there.
    credentials: tuple[Credential, ...] = ()

    def __init_subclass__(cls, **kwargs) -> None:
        """A gateway that declares a capability it cannot honour fails here, and not halfway through a pass over somebody's subscription."""
        super().__init_subclass__(**kwargs)

        if not (cls.queryable or cls.event_stated):
            raise TypeError(f"{cls.__name__} says nothing about how it answers what an account holds")

        if cls.authenticate is PaymentProvider.authenticate:
            raise TypeError(f"{cls.__name__} does not implement authenticate, and nothing else proves the caller is the gateway")

        if cls.read is PaymentProvider.read:
            raise TypeError(f"{cls.__name__} does not implement read, and nothing else can say what a call was about")

        if cls.queryable and cls.state_from_query is PaymentProvider.state_from_query:
            raise TypeError(f"{cls.__name__} says it can be queried and does not implement state_from_query")

        if not cls.credentials:
            raise TypeError(f"{cls.__name__} does not say what an operator has to paste for it")

        unknown = [credential.field for credential in cls.credentials if not hasattr(Integration, f"{credential.field}_encrypted")]

        if unknown:
            raise TypeError(f"{cls.__name__} asks for {sorted(unknown)}, which the integration has nowhere to keep")

        # Two credentials for one part leave the reader of that part picking whichever came first.
        played = [credential.role for credential in cls.credentials if credential.role]

        if len(played) != len(set(played)):
            raise TypeError(f"{cls.__name__} names more than one credential for the same part")

    def authenticate(self, integration: Integration, call: InboundCall, secret: str) -> None:
        raise NotImplementedError

    async def read(self, integration: Integration, call: InboundCall, client: httpx.AsyncClient) -> ProviderEvent | None:
        """What the call was about, and the gateway is reachable from here because a notice that carries only an id is answered by asking."""
        raise NotImplementedError

    async def state_from_query(self, secret: str, token: str, client: httpx.AsyncClient) -> list[ProviderPurchase]:
        raise NotImplementedError


class RevenueCatProvider(PaymentProvider):
    """RevenueCat posts JSON, signs what it sends, and answers over rest what an account holds at this instant."""

    API = "https://api.revenuecat.com/v1"
    SIGNATURE_HEADER = "x-revenuecat-webhook-signature"
    queryable = True

    credentials = (Credential("revenuecat_api_key", "Secret API key (v1)", "Project settings -> API keys.", API_KEY), Credential("revenuecat_webhook_secret", "Authorization header value", "Integrations -> Webhooks.", WEBHOOK_SECRET))

    ACTIONS = {
        "INITIAL_PURCHASE": NormalizedAction.ACTIVATE,
        "NON_RENEWING_PURCHASE": NormalizedAction.ACTIVATE,
        "RENEWAL": NormalizedAction.RENEW,
        "UNCANCELLATION": NormalizedAction.RESUME,
        "REFUND_REVERSED": NormalizedAction.RESUME,
        "CANCELLATION": NormalizedAction.CANCEL_AT_PERIOD_END,
        "EXPIRATION": NormalizedAction.EXPIRE,
        "BILLING_ISSUE": NormalizedAction.ENTER_GRACE,
        "SUBSCRIPTION_PAUSED": NormalizedAction.SUSPEND,
        "PRODUCT_CHANGE": NormalizedAction.CHANGE_PLAN,
        "SUBSCRIPTION_EXTENDED": NormalizedAction.EXTEND,
    }

    REFUNDED = "CUSTOMER_SUPPORT"

    def authenticate(self, integration: Integration, call: InboundCall, secret: str) -> None:
        """Two ways are offered and the secret is the same: a signed call is verified, and an unsigned one shows the header."""
        if not secret:
            return

        signature = call.header(self.SIGNATURE_HEADER)

        if signature:
            self.verify(secret, signature, call)

            return

        given = call.header("authorization")

        if not given or not matches(given, secret):
            raise AuthenticationError("error.webhook-signature-invalid")

    def verify(self, secret: str, signature: str, call: InboundCall) -> None:
        """Checks `t=<unix>,v1=<hex>` over `<t>.<raw body>`, and the body has to be the bytes that arrived: reserializing changes them."""
        moment, signatures = signature_parts(signature)

        if not moment or not signatures or not fresh(moment):
            raise AuthenticationError("error.webhook-signature-invalid")

        expected = hmac.new(secret.encode(), f"{moment}.".encode() + call.body, hashlib.sha256).hexdigest()

        if not any(matches(given, expected) for given in signatures):
            raise AuthenticationError("error.webhook-signature-invalid")

    async def read(self, integration: Integration, call: InboundCall, client: httpx.AsyncClient) -> ProviderEvent | None:
        event = call.data().get("event")

        if not isinstance(event, dict):
            return None

        return ProviderEvent(
            external_event_id=str(event.get("id") or ""),
            event_type=str(event.get("type") or ""),
            account_token=self.text(event.get("app_user_id")),
            product_reference=self.text(event.get("new_product_id") or event.get("product_id")),
            action=self.action(event),
            amount=self.money(event.get("price_in_purchased_currency")),
            currency=self.text(event.get("currency")),
            occurred_at=self.moment(event.get("event_timestamp_ms")),
        )

    def action(self, event: dict) -> NormalizedAction | None:
        """There is no refund event: it arrives as a cancellation or an expiration whose reason says the support gave the money back."""
        if event.get("cancel_reason") == self.REFUNDED or event.get("expiration_reason") == self.REFUNDED:
            return NormalizedAction.REFUND

        return self.ACTIONS.get(str(event.get("type") or ""))

    async def state_from_query(self, secret: str, token: str, client: httpx.AsyncClient) -> list[ProviderPurchase]:
        """RevenueCat is asked rather than believed, and the informational read carries no platform header so it never touches the customer's last seen."""
        answer = await client.get(f"{self.API}/subscribers/{quote(token, safe='')}", headers={"Authorization": f"Bearer {secret}"}, timeout=SUBSCRIBER_TIMEOUT)

        if answer.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise RateLimited(self.backoff(answer.headers.get("Retry-After")))

        answer.raise_for_status()

        subscriber = remote.body_of(answer).get("subscriber") or {}
        recurring = [self.recurring(product, entry) for product, entry in (subscriber.get("subscriptions") or {}).items()]
        # What never renews is listed once per purchase, and buying the same thing twice is still one thing the account holds.
        once = [self.once(product, max(entries, key=lambda entry: str(entry.get("purchase_date") or ""))) for product, entries in (subscriber.get("non_subscriptions") or {}).items() if entries]

        return recurring + once

    def recurring(self, product: str, entry: dict) -> ProviderPurchase:
        return ProviderPurchase(
            external_id=str(entry.get("store_transaction_id") or ""),
            product_reference=self.reference(product, entry),
            store=self.text(entry.get("store")),
            ownership=self.text(entry.get("ownership_type")),
            period_type=str(entry.get("period_type") or "").upper() or None,
            trial=str(entry.get("period_type") or "").upper() in TRIAL_PERIODS,
            purchased_at=self.instant(entry.get("purchase_date")),
            first_purchased_at=self.instant(entry.get("original_purchase_date")),
            period_ends_at=self.instant(entry.get("expires_date")),
            grace_ends_at=self.instant(entry.get("grace_period_expires_date")),
            auto_resume_at=self.instant(entry.get("auto_resume_date")),
            unsubscribed_at=self.instant(entry.get("unsubscribe_detected_at")),
            refunded_at=self.instant(entry.get("refunded_at")),
            environment=Environment.SANDBOX if entry.get("is_sandbox") else Environment.PRODUCTION,
        )

    def reference(self, product: str, entry: dict) -> str:
        """Names the product a purchase is of, where a Google subscription sells base plans and monthly and annual are two of them under one product id."""
        plan = self.text(entry.get("product_plan_identifier"))

        return f"{product}:{plan}" if plan else product

    def once(self, product: str, entry: dict) -> ProviderPurchase:
        """A purchase that never renews has no period, so what it grants never ends on its own."""
        return ProviderPurchase(external_id=str(entry.get("id") or ""), product_reference=product, store=self.text(entry.get("store")), purchased_at=self.instant(entry.get("purchase_date")), environment=Environment.SANDBOX if entry.get("is_sandbox") else Environment.PRODUCTION, recurring=False)

    def backoff(self, value) -> float:
        """Reads `Retry-After` as a number of seconds, because taking it for milliseconds would answer a pause of nothing and hammer them."""
        try:
            asked = float(value)
        except (TypeError, ValueError):
            return DEFAULT_BACKOFF

        return min(max(asked, DEFAULT_BACKOFF), MAX_BACKOFF)

    def instant(self, value) -> datetime | None:
        """The rest API answers ISO 8601 in UTC, where the webhook answers milliseconds."""
        if not value:
            return None

        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def moment(self, value) -> datetime | None:
        return epoch_of(value, 1000)

    def text(self, value) -> str | None:
        return str(value) if value not in (None, "") else None

    def money(self, value) -> Decimal | None:
        return Decimal(str(value)) if isinstance(value, (int, float, str)) and str(value) != "" else None


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

    PAYMENTS = {"paid": PurchaseStatus.PAID, "unpaid": PurchaseStatus.PENDING, "no_payment_required": PurchaseStatus.PAID}

    # A boleto or a debit leaves the session unpaid for days, and how it ended arrives as an event of its own.
    SESSION_OUTCOMES = {"checkout.session.async_payment_succeeded": PurchaseStatus.PAID, "checkout.session.async_payment_failed": PurchaseStatus.FAILED, "checkout.session.expired": PurchaseStatus.CANCELED}

    # A dispute moves the payment only once it settled: lost is the money gone, won is the money kept, and everything else is a dispute still being argued.
    DISPUTES = {"lost": PurchaseStatus.CHARGED_BACK, "won": PurchaseStatus.PAID}

    def authenticate(self, integration: Integration, call: InboundCall, secret: str) -> None:
        if not secret:
            return

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

    async def read(self, integration: Integration, call: InboundCall, client: httpx.AsyncClient) -> ProviderEvent | None:
        envelope = call.data()

        if envelope.get("object") != "event" or not isinstance(envelope.get("data"), dict):
            return None

        entry = envelope["data"].get("object") or {}
        event_type = str(envelope.get("type") or "")
        subscription = entry.get("object") == "subscription"

        return ProviderEvent(
            external_event_id=str(envelope.get("id") or ""),
            event_type=event_type,
            account_token=self.text((entry.get("metadata") or {}).get("account_token")),
            product_reference=self.price_of(entry) if subscription else None,
            action=self.action(event_type, entry),
            state=(self.purchase_of(entry),) if subscription else None,
            reference=self.text(entry.get("client_reference_id")),
            purchase_status=self.payment_of(event_type, entry),
            payment_id=self.text(entry.get("payment_intent")),
            amount=self.money(entry.get("amount_total"), self.text(entry.get("currency"))),
            currency=(self.text(entry.get("currency")) or "").upper() or None,
            occurred_at=self.moment(envelope.get("created")),
        )

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
            auto_resume_at=self.moment((entry.get("pause_collection") or {}).get("resumes_at")),
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


PROVIDERS: dict[Provider, PaymentProvider] = {Provider.REVENUECAT: RevenueCatProvider(), Provider.STRIPE: StripeProvider()}
