from fastkit_core.apps.loader import order_apps


async def apps_list(runtime) -> list[str]:
    return [f"{app.name} ({app.version})" for app in runtime.apps]


async def apps_graph(runtime) -> list[str]:
    ordered = order_apps(runtime.apps)
    lines = []

    for app in ordered:
        requires = ", ".join(app.requires) or "-"
        lines.append(f"{app.name} <- {requires}")

    return lines


async def run_checks(runtime) -> list[str]:
    messages = runtime.checks.run()

    if not messages:
        return ["all system checks passed"]

    return [f"[{message.level.value}] {message.message}" for message in messages]


async def routes_list(runtime) -> list[str]:
    lines = []

    for _, prefix, _, source in runtime.routers.all():
        lines.append(f"{prefix or '/'} (from {source})")

    return lines or ["no routers registered"]


async def health_report(runtime) -> list[str]:
    report = await runtime.health.run()

    return [f"{check.name}: {check.status.value}" for check in report.checks] or ["no health checks registered"]


async def db_bootstrap(runtime) -> list[str]:
    language_service = runtime.try_component("language_service")

    if language_service is None:
        return ["content app is not installed, nothing to seed"]

    created = await language_service.seed_defaults()

    return [f"seeded {created} language(s)"]


async def create_root(runtime, email: str, password: str) -> list[str]:
    account_service = runtime.component("account_service")
    password_service = runtime.component("password_service")

    user = await account_service.create_user(
        tenant_id=0,
        identifiers=[("email", email)],
        display_name=email,
        is_staff=True,
        is_root=True,
        password_hash=password_service.hash(password),
    )

    return [f"created root user {user.email} ({user.id})"]
