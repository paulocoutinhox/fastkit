# Subscriptions

What somebody pays for, what that promises, and the engine that hands it over.

## The pieces

```
Plan ──< PlanEntitlement >── Entitlement ──< Benefit
  │                                            │
Subscription ──< UserEntitlement          SubscriptionBenefit ──< BenefitGrant
```

| Row | What it is |
| --- | --- |
| `Plan` | what a subscription is sold as, written once per language and priced only so the site can show it |
| `Entitlement` | what a plan grants, named by a `code` an application gates a feature with |
| `Benefit` | what an entitlement hands over: `access`, `credit` or `product` |
| `Subscription` | what a gateway says an account holds |
| `UserEntitlement` | the right that subscription turned on |
| `SubscriptionBenefit` | the snapshot of a benefit taken at activation |
| `BenefitGrant` | one delivery of one cycle |

## One plan per market

A price is written in the currency of a market, so the same plan exists once per language: `monthly` in
USD for whoever reads in English and in BRL for whoever reads in Portuguese, under one `code`. The
listing, the plans page and the checkout all answer the row of the language the reader is in, so nobody
is ever shown one price and charged another. The language asked for wins, the configured `default_language` answers for what it
does not have, and the listing answers exactly one row per code.

The language is optional, and a plan naming none is the plan for everybody. A plan is unique over
`(COALESCE(tenant_id, 0), code, COALESCE(language_id, 0))`: in a plain unique index no null equals another, and two
plans of one code answering everybody would be a coin toss.

This is not screen translation. The name and the description of a plan are the content of that market —
whoever sells in Brazil may sell a different package at a different price.

## What a provider reported

`GET /api/subscriptions/{subscription_id}/transactions` answers a page of what the gateway said about one subscription,
and the site draws the same list a page at a time. A subscription that renews monthly for years holds one
row per notice inside the retention window, so the listing has a ceiling like every other one a client reads.

## The snapshot

Activating a subscription copies the benefits of its plan into `SubscriptionBenefit`. Editing the catalog later never rewrites what a live subscription promised. Moving to another plan ends what the new one does not list, so an upgrade never leaves somebody holding both.

## Cadence and cycles

| Cadence | When it delivers |
| --- | --- |
| `on-activation` | once, when the subscription activates |
| `recurring` | on activation and every interval after it |
| `once-per-user` | once per person, across every subscription they ever had |

A cycle that was missed is answered by `missed_cycle_policy`: `catch-up` delivers the oldest one first, `latest-only` delivers the most recent and skips the rest, `skip` resumes ahead of now.

## Idempotency

The key of a delivery is `<benefit>:<cycle>`. Replaying a pass never hands anything out twice, and each kind protects itself besides:

| Kind | What stops a second delivery |
| --- | --- |
| `credit` | the ledger is keyed by the same string, and a loser is handed the entry the winner wrote |
| `product` | owning it is one row, and a second grant finds it already held |
| `access` | turning on a right that is already on is not a second delivery |

## What ends, and what does not

When a subscription ends, the right expires and the benefits stop. **What was already handed over stays** — a product in the account is the account's for good, and credits already in the wallet are spent, not repossessed. A refund gives the money back and does not reach for either.

## Trial and grace

A plan says what it hands over while nobody has paid yet and while a payment is failing:

| Policy | What is delivered |
| --- | --- |
| `none` | nothing |
| `access-only` | only the benefit that opens access |
| `all` | everything, as if it were paid |

The default of both is `access-only`, and the reason is money: a trial that hands over what outlives it is subscribe, take, cancel.

A subscription that is paused or still pending gives no access while it stays so: its entitlements expire and its benefits are paused, and coming back turns them on again and owes the cycle it lands in, never the ones the pause covered — the date is worked out again on the way back, whatever a pass wrote on the benefit while it was paused.

A recurring interval repeats at most once a century. Every activation walks the schedule by it, and a step no calendar holds would refuse every notice of that plan, so a longer one is refused with `error.benefit-interval-too-long` when the benefit is saved.

A snapshot taken for a subscription that started long ago is scheduled from the cycle that holds today, so a first activation never pays the months before it.

## Coming back

Paying a late bill is the common case, and it owes nothing new: the same subscription resumes the same cycle. A lapse is not a cycle the engine missed either, so coming back owes the cycle it lands in and none of the ones before it, whatever the missed cycle policy says. Starting over is different, and `Plan.resume_delivery_policy` says which one a plan means. An operator can force a fresh cycle through `POST /api/subscriptions/{record_id}/new-cycle`, and who asked is written to the audit trail.
