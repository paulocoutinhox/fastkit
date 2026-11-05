from datetime import date

from pydantic import ValidationInfo, field_validator

from enums.purchase_status import PurchaseStatus
from helpers.i18n import translate
from schemas.base_schema import BaseSchema
from schemas.common import Day


class PurchasesFilter(BaseSchema):
    starts_on: Day
    ends_on: Day
    status: PurchaseStatus | None = None

    @field_validator("ends_on")
    @classmethod
    def after_the_start(cls, value: date, info: ValidationInfo) -> date:
        # A period that ends before it starts holds nothing, and answering an empty report reads as a period nobody bought anything in.
        if "starts_on" in info.data and value < info.data["starts_on"]:
            raise ValueError(translate("validation.period-reversed"))

        return value
