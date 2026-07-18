# fastkit-cli

A command-line entry point for operational tasks against a FastKit runtime.

## What it does

Boots the runtime and runs commands such as creating a superuser (`is_staff=True, is_root=True`),
seeding, and other administrative operations, using the same components (`account_service`,
`password_service`, …) the app uses.

```bash
# create a superuser
fastkit createsuperuser --email root@example.com
```

## Extending

The built-in subsystems (apps, files, tasks, reports, webhooks) each expose their own extension
mechanism. The CLI does not yet have a third-party subcommand mechanism — this is a documented
follow-up, to be implemented fully when needed rather than half-wired.
