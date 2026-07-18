from dataclasses import dataclass, field


@dataclass
class FieldError:
    field: str
    code: str
    message: str = ""
    path: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
