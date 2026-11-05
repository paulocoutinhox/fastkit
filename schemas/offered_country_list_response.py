from schemas.base_schema import BaseSchema
from schemas.offered_country_schema import OfferedCountrySchema


class OfferedCountryListResponse(BaseSchema):
    items: list[OfferedCountrySchema]
