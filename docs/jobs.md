# Jobs

The scheduler is [Queuefy](https://github.com/paulocoutinhox/queuefy), with its runs in the same database the application uses. Every node sees the same schedule, and exactly one of them claims each run.

## What runs

| Job | When | Queue | What it does |
| --- | --- | --- | --- |
| `run_subscription_cycle` | every 5 min | `subscription` | one pass over subscriptions, in the order below |
| `process_pending_events` | every 10 min | `event` | closes what the clients reported |
| `send_pending_emails` | every 2 min | `email` | sends what is in the mail queue, readable in the admin under Outbound Emails |
| `discard_expired_records` | 04:20 | `retention` | drops what no rule will ever read again |
| `discard_orphan_files` | 04:40 | `storage` | deletes what this application wrote down and nothing ever claimed |

## The order of a subscription pass

1. The `reconciliation_service.reconcile_stale` pass — the provider speaks before the clock closes anything
2. The `delivery_service.expire_subscriptions` pass — what the provider did not save, the clock closes
3. The `delivery_service.process_due` pass — what is still open is delivered
4. The `delivery_service.retry_failed_grants` pass — a delivery that failed or was abandoned is picked up
5. The `webhook_service.retry_failed` pass — the same, on the gateway side

The order is the point. Expiring before asking would close a subscription that renewed while nobody was looking.

## An operational table stops growing

An installation that runs for years is one that still answers, and what stops it is not load — it is a table nobody ever trimmed. The audit trail gains two rows per cron pass, the apps report events in batches, every gateway notice is kept whole, and the queue writes a row per occurrence of every job.

`RetentionSettings` says how long each one keeps what it holds, and **zero keeps it forever**:

| Table | Default | What goes |
| --- | --- | --- |
| `system_log` | 180 days | any row, because it is a record and not a state |
| `app_event` | 90 days | what closed, plus what failed and spent every attempt |
| `integration_webhook_event` | 90 days | the same, and the window is far longer than any gateway redelivers for |
| `outbound_email` | 90 days | what went out, plus what failed and spent every attempt |
| `queuefy_run` | 30 days | a settled run, through the library's own purge |
| `cachefy_entry` | on expiry | an assembled answer nobody may be served again, through the library's own purge |

Nothing in flight is ever dropped: a row leaves only when no rule will look at it again, so whatever a retry could still pick up stays however old it is. The delete walks out a thousand rows at a time — the first pass over a table nobody ever trimmed would otherwise hold it for minutes.

## Exactly once

Every worker computes the next slot of a recurring task and writes it under a unique key. The database keeps one, and the rest are told it is taken. Claiming a run is a conditional write only one of them wins. Nothing elects a leader, because nothing needs to.

The `cron_queues` setting splits **load** between instances and never guarantees correctness — that is what the claim is for. Left empty, an instance serves every queue its jobs declare.

## An address the server refused stops receiving

Only a refusal **of the recipient** suppresses an address. Our own credentials being wrong answers 5xx
too, and suppressing a real reader because of that would be silent.

| What the server says | What happens |
| --- | --- |
| 5xx refusing the recipient | the message ends as `refused`, and the address is suppressed |
| 4xx | tried again, as always |
| 5xx on authentication or on the sender | tried again: the configuration is wrong, not the reader |

The queue does not dial a suppressed address. It writes the row as `refused` so the attempt leaves a
trace, and the suppression list is never trimmed by retention — it is what stops writing to the same
dead address forever.

## A sweep belongs to whoever runs alone

Reclaiming what a dead node left reserved is a write over a whole table, and it lives in the job rather than in the pass every node walks. Sixteen nodes running that sweep inside the send loop deadlocked and stranded messages in `sending`, and the same sixteen with the sweep in the job sent every message once. The occurrence of a cron is claimed by one node, so that node is the one that sweeps before it works.

The rule outlives the case: a write over a whole table belongs to whoever runs alone. When one sits in the path every node walks, what gets fixed is where it lives — never the error it raises.

## Running one by hand

```bash
make delivery
```

That calls the very same function the cron calls. Which is why the row-level guards still matter: somebody running it by hand while the cron fires is a race the queue never sees.

## The trail

The worker announces every run, and those announcements become rows of `system_log` in the `cron` category: an entry when it starts, one with the duration when it finishes, one with the message when it fails. A listener that breaks breaks alone — an audit trail that fails must never take the outcome of a job with it.
