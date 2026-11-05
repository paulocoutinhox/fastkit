from datetime import date

from pydantic import ValidationInfo, field_validator

from enums.provider import Provider
from enums.subscription_status import SubscriptionStatus
from helpers.i18n import translate
from schemas.base_schema import BaseSchema
from schemas.common import Day


class SubscriptionsFilter(BaseSchema):
    status: SubscriptionStatus | None = None
    provider: Provider | None = None
    started_from: Day | None = None
    started_until: Day | None = None

    @field_validator("started_until")
    @classmethod
    def after_the_start(cls, value: date | None, info: ValidationInfo) -> date | None:
        # A period that ends before it starts holds nothing, and answering an empty report reads as a period nobody subscribed in.
        if value is not None and info.data.get("started_from") is not None and value < info.data["started_from"]:
            raise ValueError(translate("validation.period-reversed"))

        return value
