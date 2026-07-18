from urllib.parse import urlencode


def resolve_route(sub: str) -> tuple[str, dict]:
    """Map an admin sub-path to a screen kind and its arguments."""

    parts = [part for part in sub.split("/") if part]

    if not parts:
        return "dashboard", {}

    if len(parts) == 1:
        if parts[0] == "profile":
            return "profile", {}

        return "list", {"resource": parts[0]}

    if len(parts) == 2:
        if parts[0] == "reports":
            return "report", {"name": parts[1]}

        if parts[1] == "new":
            return "form", {"resource": parts[0], "record_id": None, "mode": "create"}

        return "detail", {"resource": parts[0], "record_id": parts[1]}

    if len(parts) == 3 and parts[2] == "edit":
        return "form", {"resource": parts[0], "record_id": parts[1], "mode": "edit"}

    return "notfound", {}


def screen_query(params) -> str:
    items = [(key, value) for key, value in params.multi_items() if key != "_fragment"]

    return f"?{urlencode(items)}" if items else ""


def nav_current(kind: str, args: dict) -> str | None:
    if kind == "dashboard":
        return "dashboard"

    if kind in ("list", "form", "detail"):
        return args.get("resource")

    if kind == "report":
        return args.get("name")

    return None


def build_header(kind: str, args: dict, path: str, t, label: str | None = None, display: str | None = None, report_title: str | None = None) -> tuple[list[dict], str]:
    home = {"label": t("nav.home"), "url": path}

    if kind == "dashboard":
        return [], t("dashboard.title")

    if kind == "profile":
        title = t("profile.title")

        return [home, {"label": title, "url": None}], title

    if kind == "report":
        title = t(report_title)

        return [home, {"label": title, "url": None}], title

    resource = args.get("resource")
    resource_label = t(label) if label else resource
    resource_crumb = {"label": resource_label, "url": f"{path}/{resource}"}

    if kind == "list":
        return [home, {"label": resource_label, "url": None}], resource_label

    if kind == "form":
        prefix = t("grid.new") if args.get("mode") == "create" else t("form.edit")
        title = f"{prefix} {resource_label}"

        return [home, resource_crumb, {"label": prefix, "url": None}], title

    leaf = display or str(args.get("record_id"))

    return [home, resource_crumb, {"label": leaf, "url": None}], leaf
