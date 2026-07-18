from dataclasses import dataclass


@dataclass
class Fieldset:
    title: str | None
    fields: list[str]
    description: str | None = None
