import argparse

from fastkit_cli import commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fastkit", description="FastKit command line interface"
    )
    sub = parser.add_subparsers(dest="group", required=True)

    apps = sub.add_parser("apps").add_subparsers(dest="action", required=True)
    apps.add_parser("list")
    apps.add_parser("graph")

    sub.add_parser("checks")
    sub.add_parser("routes")
    sub.add_parser("health")

    db = sub.add_parser("db").add_subparsers(dest="action", required=True)
    db.add_parser("bootstrap")

    admin = sub.add_parser("admin").add_subparsers(dest="action", required=True)
    create_root = admin.add_parser("create-root")
    create_root.add_argument("--email", required=True)
    create_root.add_argument("--password", required=True)

    return parser


async def dispatch(runtime, args: argparse.Namespace) -> list[str]:
    if args.group == "apps" and args.action == "list":
        return await commands.apps_list(runtime)

    if args.group == "apps" and args.action == "graph":
        return await commands.apps_graph(runtime)

    if args.group == "checks":
        return await commands.run_checks(runtime)

    if args.group == "routes":
        return await commands.routes_list(runtime)

    if args.group == "health":
        return await commands.health_report(runtime)

    if args.group == "db" and args.action == "bootstrap":
        return await commands.db_bootstrap(runtime)

    return await commands.create_root(runtime, args.email, args.password)


async def run(runtime, argv: list[str]) -> tuple[int, list[str]]:
    args = build_parser().parse_args(argv)
    lines = await dispatch(runtime, args)

    return 0, lines
