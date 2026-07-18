# FastKit documentation

FastKit is a modular, asynchronous ecosystem for FastAPI applications, shipped as a monorepo of
independently versioned Python distributions. A consumer project installs only the packages it
needs and contributes apps, models, admin resources, providers and system checks through public
registries and contracts. Business rules live in the consumer project — FastKit provides generic,
predictable infrastructure.

This directory is the **consumer documentation**: how to use and extend every part of FastKit, with
examples. For the framework's internal engineering conventions and invariants, see
[`CLAUDE.md`](../CLAUDE.md) at the repository root.

## How this documentation is organized

Each file covers one topic. Start with **Getting started**, skim **Concepts**, then dive into the
**package** or **admin** area you need. The **Guides** are task-oriented ("how do I add X?").

### Getting started
- [Overview](getting-started/overview.md) — what FastKit is and how the pieces fit
- [Installation](getting-started/installation.md) — environment, commands, services
- [Project setup](getting-started/project-setup.md) — wiring a consumer project end to end
- [Configuration](getting-started/configuration.md) — settings from TOML + environment

### Concepts
- [Apps and lifecycle](concepts/apps-lifecycle.md)
- [Runtime and registries](concepts/runtime-registries.md)
- [Service container](concepts/service-container.md)
- [Request context](concepts/request-context.md)
- [Response envelope](concepts/response-envelope.md)
- [Errors and i18n](concepts/errors-and-i18n.md)
- [Events](concepts/events.md)
- [Health and system checks](concepts/health-checks.md)
- [Resilience](concepts/resilience.md)
- [Providers](concepts/providers.md)

### Data
- [Database](data/database.md)
- [Models and mixins](data/models-and-mixins.md)
- [Conventions](data/conventions.md)

### Packages
- [core](packages/core.md) · [config](packages/config.md) · [db](packages/db.md) ·
  [logging](packages/logging.md) · [tenancy](packages/tenancy.md) · [accounts](packages/accounts.md) ·
  [permissions](packages/permissions.md) · [auth](packages/auth.md) · [cache](packages/cache.md) ·
  [storage](packages/storage.md) · [files](packages/files.md) · [tasks](packages/tasks.md) ·
  [mail](packages/mail.md) · [i18n](packages/i18n.md) · [content](packages/content.md) ·
  [admin](packages/admin.md) · [reports](packages/reports.md) · [webhooks](packages/webhooks.md) ·
  [cli](packages/cli.md) · [testkit](packages/testkit.md) · [vendor packages](packages/vendors.md)

### Admin
- [Resources](admin/resources.md) · [Fields](admin/fields.md) · [Filters](admin/filters.md) ·
  [Columns](admin/columns.md) · [Actions](admin/actions.md) · [Inlines](admin/inlines.md) ·
  [Related-object widget](admin/related-widget.md) · [Dependent selects & lookups](admin/dependent-selects.md) ·
  [Uploads & file fields](admin/uploads-files.md) · [Overrides](admin/overrides.md) ·
  [Permissions](admin/permissions.md) · [Templates & rendering](admin/templates-rendering.md) ·
  [Client (app.js)](admin/client-js.md) · [Dashboard](admin/dashboard.md) ·
  [Reports in the admin](admin/reports-in-admin.md) · [Login & captcha](admin/login-and-captcha.md) ·
  [Theme & branding](admin/theme.md) · [Translations](admin/translations.md)

### Guides (how-to)
- [Add an app](guides/add-an-app.md)
- [Add a model and admin resource](guides/add-model-and-resource.md)
- [Add a custom field type](guides/custom-field.md)
- [Add a custom filter](guides/custom-filter.md)
- [Add a custom action](guides/custom-action.md)
- [Add a report and exporters](guides/add-report.md)
- [Handle uploads (image / file / avatar)](guides/handle-uploads.md)
- [Configure storage (local / S3 / R2)](guides/configure-storage-local-s3-r2.md)
- [Add a cache provider](guides/add-cache-provider.md)
- [Add a mail provider](guides/add-mail-provider.md)
- [Add a captcha provider](guides/add-captcha-provider.md)
- [Customize the login screen](guides/customize-login.md)
- [Add a locale / translations](guides/add-locale.md)
- [Scheduled tasks and the worker](guides/scheduled-tasks-worker.md)
- [Multitenant login](guides/multitenant-login.md)
- [Extend the admin client](guides/extend-admin-client.md)
- [Override admin templates](guides/override-templates.md)

### Reference
- [Settings reference](reference/settings.md)
- [Error codes](reference/error-codes.md)
- [Response envelope shape](reference/envelope-shape.md)
- [CLI commands](reference/cli-commands.md)

## The reference application

Everything documented here is exercised by [`examples/demo`](../examples/demo), the reference app
that wires every package together. When an example in these docs is abridged, the demo has the full,
running version.
