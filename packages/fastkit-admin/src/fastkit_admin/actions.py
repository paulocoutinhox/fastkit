from dataclasses import dataclass


@dataclass(frozen=True)
class AdminAction:
    """A custom action a resource exposes on a row or in bulk, run by `action_<name>`."""

    name: str
    label: str
    scope: str = "row"
    permission: str | None = None
    variant: str = "secondary"
    confirm: bool = False
    confirm_message: str | None = None
    icon: str | None = None

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "scope": self.scope,
            "variant": self.variant,
            "confirm": self.confirm,
            "confirm_message": self.confirm_message,
            "icon": self.icon,
        }
