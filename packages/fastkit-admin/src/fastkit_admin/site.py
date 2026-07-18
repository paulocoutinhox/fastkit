from dataclasses import dataclass

from fastkit_core.errors.codes import RESOURCE_NOT_FOUND
from fastkit_core.errors.exceptions import NotFoundError


@dataclass
class MenuGroup:
    key: str
    label: str
    order: int = 0
    icon: str | None = None


@dataclass
class MenuItem:
    label: str
    group: str = "general"
    resource: str | None = None
    path: str | None = None
    icon: str = "dot"
    permission: str | None = None
    order: int = 0


class AdminSite:
    """Registry of admin resources plus consumer-defined, permission-aware navigation."""

    def __init__(self, name: str = "main", title: str = "Administration", path: str = "/admin", api_path: str = "/api"):
        self.name = name
        self.title = title
        self.path = path
        self.api_path = api_path
        self._resources: dict[str, object] = {}
        self._groups: dict[str, MenuGroup] = {}
        self._items: list[MenuItem] = []

    def register(self, resource) -> None:
        if resource.name in self._resources:
            raise ValueError(f"admin resource '{resource.name}' is already registered")

        self._resources[resource.name] = resource

    def get(self, name: str):
        resource = self._resources.get(name)

        if resource is None:
            raise NotFoundError(RESOURCE_NOT_FOUND, message=f"admin resource '{name}' not found")

        return resource

    def find(self, name: str):
        return self._resources.get(name)

    def resources(self) -> list:
        return list(self._resources.values())

    def add_group(self, key: str, label: str, order: int = 0, icon: str | None = None) -> None:
        self._groups[key] = MenuGroup(key=key, label=label, order=order, icon=icon)

    def add_menu(self, label: str, group: str = "general", resource: str | None = None, path: str | None = None, icon: str | None = None, permission: str | None = None, order: int = 0) -> None:
        if icon is None:
            icon = getattr(self._resources.get(resource), "icon", "point") or "point"

        self._items.append(MenuItem(label=label, group=group, resource=resource, path=path, icon=icon, permission=permission, order=order))

    def _effective_permission(self, item: MenuItem) -> str | None:
        if item.permission is not None:
            return item.permission

        resource = self._resources.get(item.resource) if item.resource is not None else None

        return resource.permissions.get("list") if resource is not None else None

    async def navigation(self, check) -> list[dict]:
        """Build the grouped navigation, keeping only items the user may see and non-empty groups."""

        visible: dict[str, list[MenuItem]] = {}

        for item in self._items:
            permission = self._effective_permission(item)

            if permission is not None and not await check(permission):
                continue

            visible.setdefault(item.group, []).append(item)

        groups = []

        for key in sorted(visible, key=lambda group_key: (self._group_order(group_key), group_key)):
            items = sorted(visible[key], key=lambda item: (item.order, item.label))
            group = self._groups.get(key)

            groups.append(
                {
                    "key": key,
                    "label": group.label if group else key.title(),
                    "icon": group.icon if group else None,
                    "items": [{"label": item.label, "resource": item.resource, "path": item.path, "icon": item.icon} for item in items],
                }
            )

        return groups

    def _group_order(self, key: str) -> int:
        group = self._groups.get(key)

        return group.order if group else 1000
