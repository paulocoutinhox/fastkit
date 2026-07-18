from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError


def _fail(field: str, code: str) -> ValidationError:
    return ValidationError(
        VALIDATION_FAILED, field_errors=[FieldError(field=field, code=code)]
    )
