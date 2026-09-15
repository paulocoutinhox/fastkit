# Payment gateways

A gateway is a class. Nothing outside it decides what a subscription is.

## The contract

```python
class PaymentProvider:
    queryable = False  # it can be asked what an account holds right now
    event_stated = False  # its own notice carries enough to say so
    credentials = ()  # what an operator pastes, named the way its panel names it

    def authenticate(self, integration, call, secret) -> None: ...
    async def read(self, integration, call, client) -> ProviderEvent | None: ...
    async def state_from_query(self, secret, token, client) -> list[ProviderPurchase]: ...
```

The secret is handed in rather than fetched, and so is the HTTP client: a gateway is a class that never reaches back into a service, which is what keeps a new one from having any power over the rules.

A class that declares a capability it cannot honour fails at import, where the declaration is, and not halfway through a pass over somebody's subscription.

Whatever a provider returns, exactly one function writes state: `ReconciliationService.apply`. That is why adding a gateway changes no business rule.

## The address

One URL per tenant and per gateway:

```
GET POST PUT PATCH DELETE  /api/webhooks/{key}
```

The key is drawn when the integration is created and is never editable. The route accepts the call however it arrives — method, body format, headers — because the gateway decides all of that and we decide none of it. The event is written down and committed **before** anything is read from it: losing what arrived is worse than failing to read it.

## RevenueCat

Queryable. Its notice is a trigger, and what the subscriber endpoint answers is what gets written — which makes the result immune to a lost, duplicated or out-of-order event.

| What it sends | Where it goes |
| --- | --- |
| `id` | the idempotency key |
| `app_user_id` | the account token the app handed to `logIn` |
| `product_id` / `new_product_id` | the external product, the newer one winning |
| `price_in_purchased_currency` + `currency` | what the buyer actually paid |

The `price` field is the amount in dollars and is never stored: storing it beside the buyer's currency says somebody paid 4.20 reais for a 19.90 subscription.

Authentication is `X-RevenueCat-Webhook-Signature` (`t=…,v1=…`, HMAC-SHA256 over `<t>.<raw body>`) or a plain `Authorization` header. There is no time window, because they redeliver for over an hour and refusing by age would drop a legitimate retry.

## Stripe

Event-stated. The notice carries the object, so nothing is asked.

| Event | What it means here |
| --- | --- |
| `customer.subscription.created` | a subscription opens |
| `customer.subscription.updated` | the state is rewritten from the object |
| `customer.subscription.deleted` | it ends |
| `checkout.session.completed` | a payment mode session settles a purchase of ours |
| `checkout.session.async_payment_succeeded` / `async_payment_failed` | how a delayed payment ended, days later |
| `checkout.session.expired` | the session died with nobody paying |
| `invoice.paid` / `invoice.payment_failed` | recorded, and the state comes from the subscription events |

The current period lives on the **subscription item** (`items.data[].current_period_start/end`), which is where Stripe moved it. Every status they name maps to one of ours, and an amount is read in the units of its own currency — a zero-decimal currency has no cents, and dividing one by a hundred says somebody paid a hundredth of what they did.

Authentication is `Stripe-Signature`: HMAC-SHA256 over `<t>.<raw body>`, only the `v1` scheme, every `v1` accepted because a secret being rolled is signed twice, and a five-minute tolerance — Stripe stamps a fresh timestamp on every retry, so an old one is a replay.

A body without `"object": "event"` at the top is not a notice and nothing is read from it, and `data.object.object` — `subscription` or `checkout.session` — is what says which of the two lives it is about. Which account a notice concerns comes from `metadata.account_token`, which the checkout puts on both the session and the subscription. A reference this side minted comes back as `client_reference_id`, a string and never the id of the row, and resolving it is the work of a service and never of a gateway: a provider never touches the database.

## A notice is about one thing

A query answer lists everything an account holds, so what is missing from it has ended. A notice is about the one purchase it names, so nothing else the account holds is closed by its silence. The reconciliation is told which of the two it is looking at.

## Adding one

Write the class, name its credentials after its own panel, add the two encrypted columns to `Integration`, and register it. Nothing else changes — proved by a suite that wires two differently-shaped gateways into the same tenant and follows a purchase from the notice all the way to what the account owns.
