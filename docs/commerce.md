# Commerce

What is sold once, and what owning it means.

## Product

A product is bought once and owned for good. It carries a price, an image, an optional file the owner may download, and the credits owning it puts in a balance of the currency it names.

Credits are a property of the product and not of the way it was obtained, so a pack bought at checkout and the same pack handed over by a plan both move the balance the same way. That is one rule in one place: `commerce_service.grant`.

## Purchase

A purchase is written on this side **before** the buyer is sent anywhere, because what a gateway echoes back has to name a row that already exists. It carries a `reference` this side minted and, once the gateway answers, the id the gateway calls it by.

```
open_purchase   ->  the buyer goes to the gateway
                ->  the gateway notices back
                ->  settle_purchase(PAID)
                ->  the product is handed over and its credits move
```

Settling the same status twice is not a second delivery. Settling a refund marks the payment and reaches for nothing.

The money can also go back after all of that, and two notices say so. A charge the gateway reports as
**fully** refunded marks the purchase refunded — a partial one leaves it where it stands, because half the
money back is not a purchase undone. A dispute marks it charged back only once it is **lost**, and puts it
back to paid when it is won: a dispute that was merely opened has taken nothing. Neither notice carries the
reference this side minted, so what names the purchase is the payment id stored when the session settled,
which is the same id those notices carry.

Not every payment method finishes while the buyer is watching. A delayed one — a boleto, a bank debit — sends them back with the purchase still pending and says how it ended days later, so the page they land on reads the row rather than congratulating them, and a purchase that is already settled is never walked back by a notice that arrives after the money did.

A session the gateway refuses is a buyer who never left, so the row this side opened is marked failed
before the error goes up. Left pending it would wait for a notice nobody was ever going to send, and show
on the purchases of the account as a payment in progress that never existed.

## Sending the same checkout twice

An application that retries a `POST` would open a second session at the gateway and a second purchase.
Both checkout routes honour an `Idempotency-Key` header, and the key is claimed **before** the work
starts — two calls that merely looked first would both do the work.

| What the key finds | What the route answers |
| --- | --- |
| nobody claimed it | this call does the work and keeps its answer on the key |
| it already carries an answer | that same answer, opening nothing |
| claimed, still no answer | 409, because the first call is still answering |
| claimed over five minutes ago, still no answer | this call takes it over, because the first one died |
| claimed by another route | 409, because a key names one write and not two |

A key belongs to the account that used it, so two clients never share a namespace.

Taking over a key a dead call left behind is a conditional `UPDATE` and not a read followed by a
decision: two calls that both read the same expired window would both do the work, which is the one
thing the key exists to prevent. The window is measured from when the work was claimed, so a takeover
moves that moment and the next call does not find it expired all over again.

The keys are an operational table like any other, so a key that already carries its answer is dropped
after `retention.client_request_days`.

## Currencies and balances

A currency is a record, not a fixed pair: whatever the product decides to call it, scoped to a tenant like everything else. An account holds one balance per currency, and every currency has a ledger of its own that is append-only. A balance is corrected by another movement and never by editing one, because `balance_after` on every line is what makes the ledger explain the balance.

| Type | Direction |
| --- | --- |
| `credit` | always adds |
| `debit` | always subtracts |
| `reversal` | always subtracts |
| `adjustment` | whatever sign it was given |

A directed movement takes a magnitude and never a sign. A negative amount on a credit, a debit or a
reversal is refused rather than read as its opposite, which is what used to turn minus fifty on a credit
into fifty landing in the wallet. The balance has a ceiling for the same reason it has a floor: one below
zero is a balance nobody holds, and one above what the column keeps overflows inside the driver.

An amount reaches a gateway as a whole number of the smallest unit its currency has, rounded rather than cut short, because truncating one that keeps none charges less than the page said. Every column that holds money keeps three decimals, which is what the finest currency divides into: two would round away what a dinar is priced at and what a gateway reported being paid.

## What the API answers

| Path | Who | What |
| --- | --- | --- |
| `GET /api/commerce/products?search=` | anybody with a tenant | what that tenant sells, optionally searched by name or slug, marked with what the caller owns |
| `GET /api/commerce/products/{slug}` | anybody with a tenant | one of them |
| `GET /api/account/products` | the account | what it owns, with the download address built here and nowhere else |
| `GET /api/account/purchases` | the account | what it paid for |
| `GET /api/account/credits` | the account | its own ledger |
| `GET /api/purchases` | an administrator | every payment, read only |

The address of a downloadable file is only ever built on the surface that already knows the caller owns it.

The shared cache keeps the assembled catalogue without `owned`, because ownership belongs to one account.
Each request adds that field after reading the shared value, so one person's ownership can never appear in
another person's answer. A search term is part of the cache key rather than a filter applied to a cached
full catalogue.
