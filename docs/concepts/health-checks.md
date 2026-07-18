# Health and system checks

FastKit distinguishes **health checks** (is a dependency reachable right now?) from **system checks**
(is the deployment configured sanely?).

## Health checks

Register a probe during bootstrap:

```python
def register_services(self, context):
    context.health.register("cache", lambda: self._health(context))
```

`HealthCheckRegistry.run` executes every probe and returns a report. Each probe is **isolated**: a
raising probe is caught and reported `unavailable` with its error detail — a broken probe degrades
the report, it never 500s `/health`.

Providers register a health check that resolves the **live** component at check time
(`context.component("cache")`/`context.component("storage")`), so a consumer that overrides the
provider via `set_component` gets a health check for **its** provider, not the discarded framework
one.

Statuses map to `healthy` / `degraded` / `unavailable`.

## System checks

System checks validate configuration and wiring at startup (for example: a required secret is set, a
storage bucket is configured). They surface misconfiguration early rather than at first use.

## Consuming the report

Mount the health endpoint your project exposes; it calls `HealthCheckRegistry.run` and returns the
aggregated report. Because probes are isolated, the endpoint always responds — the report tells you
which dependency is down.
