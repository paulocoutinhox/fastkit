from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError


class AdminField:
    """Base admin field describing how a value is edited, displayed and parsed."""

    field_type = "text"

    def __init__(
        self,
        name: str,
        label: str | None = None,
        required: bool = False,
        readonly: bool = False,
        help_text: str | None = None,
        placeholder: str | None = None,
        default=None,
        write_only: bool = False,
        virtual: bool = False,
        hide_label: bool = False,
    ):
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.required = required
        self.readonly = readonly
        self.help_text = help_text
        self.placeholder = placeholder
        self.default = default
        self.write_only = write_only
        self.virtual = virtual
        self.hide_label = hide_label

    def to_schema(self) -> dict:
        return {
            "name": self.name,
            "type": self.field_type,
            "label": self.label,
            "required": self.required,
            "readonly": self.readonly,
            "help_text": self.help_text,
            "placeholder": self.placeholder,
            "default": self.default,
            "virtual": self.virtual,
            "hide_label": self.hide_label,
        }

    def format_value(self, value, locale: str = "en"):
        return value

    def parse_value(self, raw, locale: str = "en"):
        return raw

    def _fail(self, code: str) -> ValidationError:
        return ValidationError(
            VALIDATION_FAILED, field_errors=[FieldError(self.name, code)]
        )

    def validate(self, value) -> None:
        if self.required and (value is None or value == ""):
            raise self._fail("validation.required")
