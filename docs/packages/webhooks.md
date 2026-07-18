# fastkit-webhooks

Receive, verify, store and process inbound webhooks with signature checking and safe retries.

## Flow

1. A webhook arrives; the signature is verified.
2. A valid-signed payload is stored `received`; a bad signature or a non-JSON / non-object body is
   stored **rejected** (never raised — a replayed bad-signature payload can't 500).
3. `process(event_id)` runs the handler.

## Exactly-once claim

`process()` claims with a **CAS**: a conditional `UPDATE … WHERE status IN (received, retrying)`
(`rowcount == 1`) **before** running the handler, so two concurrent `process(event_id)` calls can't
both run the side effect or double-count `attempt_count`.

## Idempotent storage

`_store_valid` and `_store_rejected` insert-first then catch `IntegrityError` and re-fetch — a
replayed payload is idempotent.

## Handlers

Register handlers in the webhooks registry (its own registry, like tasks/reports). A handler's own
error retries; a genuinely bad event is stored rejected.
