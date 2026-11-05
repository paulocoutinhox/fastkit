import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx2

from enums.environment import Environment
from enums.normalized_action import NormalizedAction
from helpers.authentication_error import AuthenticationError
from helpers.dates import now
from models.base import Money
from models.integration import Integration
from services.credential import Credential
from services.inbound_call import InboundCall
from services.payment_provider import PaymentProvider
from services.provider_event import ProviderEvent
from services.provider_purchase import ProviderPurchase
from services.rate_limited import RateLimited
from services.silent import Silent

# How long a gateway is given to answer a question about one account.
SUBSCRIBER_TIMEOUT = 10.0


# What RevenueCat calls a period the buyer is not paying full price for, which is a trial in our terms.
TRIAL_PERIODS = ("TRIAL", "INTRO")


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
    except (TypeError, ValueError, OverflowError, OSError):
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


# The key that reads the gateway, and the value that proves a call came from it.
API_KEY, WEBHOOK_SECRET = "api_key", "webhook_secret"


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
        # A notice here only says which account to ask about, so one that arrives with nothing configured to check it moves nothing the query would not.
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

    async def read(self, integration: Integration, call: InboundCall, client: httpx2.AsyncClient) -> ProviderEvent | None:
        event = call.data().get("event")

        if not isinstance(event, dict):
            return None

        if event.get("type") == "TRANSFER":
            return self.transfer(event)

        return ProviderEvent(
            external_event_id=str(event.get("id") or ""),
            event_type=str(event.get("type") or ""),
            account_token=self.text(event.get("app_user_id")),
            product_reference=self.text(event.get("new_product_id") or event.get("product_id")),
            action=self.action(event),
            amount=self.money(event.get("price_in_purchased_currency"), self.currency(event.get("currency"))),
            currency=self.currency(event.get("currency")),
            occurred_at=self.moment(event.get("event_timestamp_ms")),
        )

    def transfer(self, event: dict) -> ProviderEvent:
        """A transfer names no app user, only who the purchases left and who received them, and it is sent once, for the account receiving them."""
        receiving = self.accounts(event.get("transferred_to"))
        leaving = self.accounts(event.get("transferred_from"))

        return ProviderEvent(external_event_id=str(event.get("id") or ""), event_type="TRANSFER", account_token=receiving[0] if receiving else None, also_about=(*receiving[1:], *leaving), occurred_at=self.moment(event.get("event_timestamp_ms")))

    def accounts(self, value) -> list[str]:
        return [str(token) for token in value if token not in (None, "")] if isinstance(value, list) else []

    def action(self, event: dict) -> NormalizedAction | None:
        """There is no refund event: it arrives as a cancellation or an expiration whose reason says the support gave the money back."""
        if event.get("cancel_reason") == self.REFUNDED or event.get("expiration_reason") == self.REFUNDED:
            return NormalizedAction.REFUND

        return self.ACTIONS.get(str(event.get("type") or ""))

    async def state_from_query(self, secret: str, token: str, client: httpx2.AsyncClient) -> list[ProviderPurchase]:
        """RevenueCat is asked rather than believed, and the informational read carries no platform header so it never touches the customer's last seen."""
        answer = await client.get(f"{self.API}/subscribers/{quote(token, safe='')}", headers={"Authorization": f"Bearer {secret}"}, timeout=SUBSCRIBER_TIMEOUT)

        if answer.status_code == httpx2.codes.TOO_MANY_REQUESTS:
            raise RateLimited(self.backoff(answer.headers.get("Retry-After")))

        answer.raise_for_status()

        subscriber = self.customer_snapshot(answer)
        recurring = [self.recurring(product, entry) for product, entry in subscriber["subscriptions"].items()]
        # What never renews is listed once per purchase, and buying the same thing twice is still one thing the account holds.
        once = [self.once(product, max(entries, key=lambda entry: str(entry.get("purchase_date") or ""))) for product, entries in subscriber["non_subscriptions"].items() if entries]

        return recurring + once

    def customer_snapshot(self, answer: httpx2.Response) -> dict:
        try:
            envelope = answer.json()
        except (ValueError, RecursionError) as error:
            raise Silent("RevenueCat returned an invalid customer snapshot") from error

        if not isinstance(envelope, dict) or not isinstance(envelope.get("subscriber"), dict):
            raise Silent("RevenueCat returned an invalid customer snapshot")

        subscriber = envelope["subscriber"]
        subscriptions = subscriber.get("subscriptions")
        non_subscriptions = subscriber.get("non_subscriptions")

        if not isinstance(subscriptions, dict) or not isinstance(non_subscriptions, dict):
            raise Silent("RevenueCat returned invalid purchase collections")

        for entry in subscriptions.values():
            self.validate_purchase(entry, recurring=True)

        for entries in non_subscriptions.values():
            if not isinstance(entries, list):
                raise Silent("RevenueCat returned invalid non-subscription purchases")

            for entry in entries:
                self.validate_purchase(entry, recurring=False)

        return subscriber

    def validate_purchase(self, entry, recurring: bool) -> None:
        if not isinstance(entry, dict) or not isinstance(entry.get("purchase_date"), str):
            raise Silent("RevenueCat returned an invalid purchase")

        if recurring and "expires_date" not in entry:
            raise Silent("RevenueCat returned a subscription without its expiration")

        dates = ("purchase_date", "original_purchase_date", "expires_date", "grace_period_expires_date", "auto_resume_date", "unsubscribe_detected_at", "refunded_at")

        for field in dates:
            value = entry.get(field)

            if value is None:
                continue

            moment = self.instant(value) if isinstance(value, str) else None

            if moment is None or moment.tzinfo is None or moment.utcoffset() is None:
                raise Silent("RevenueCat returned an invalid purchase date")

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

    def currency(self, value) -> str | None:
        """A currency is the three letters of its code, and anything else read here is what an unsigned notice made up."""
        code = self.text(value)

        return code.upper() if code is not None and len(code) == 3 and code.isascii() and code.isalpha() else None

    def money(self, value, currency: str | None) -> Decimal | None:
        """An amount is worth something only next to the currency it is in, and a value that is not a finite number, or one past what the column holds, is no amount at all."""
        if currency is None or isinstance(value, bool) or not isinstance(value, (int, float, str)):
            return None

        try:
            amount = Decimal(str(value))
        except InvalidOperation:
            return None

        return amount if amount.is_finite() and abs(amount) < Decimal(10) ** (Money.precision - Money.scale) else None
