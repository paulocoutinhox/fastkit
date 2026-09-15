from fastapi import APIRouter

from helpers import postal_code
from helpers.auth import CurrentUser
from helpers.crud import build_router
from helpers.db import DatabaseSession
from helpers.errors import NotFoundError
from schemas.common import BaseSchema
from schemas.country import CountryCreate, CountrySchema, CountryUpdate, OfferedCountrySchema, PostalAddressSchema
from services.country import country_service

public_router = APIRouter(prefix="/countries", tags=["countries"])


class OfferedCountryListResponse(BaseSchema):
    items: list[OfferedCountrySchema]


@public_router.get("/offered", response_model=OfferedCountryListResponse, summary="List the countries an address may be written in")
async def list_offered(db: DatabaseSession):
    """What an address form is offered, and which of those countries have somebody to ask about a postal code."""
    offered = await country_service.list_offered(db)

    return OfferedCountryListResponse(items=[OfferedCountrySchema.model_validate(country) for country in offered])


@public_router.get("/{country_code}/postal-code/{code}", response_model=PostalAddressSchema, summary="Read what a postal code stands for")
async def read_postal_code(db: DatabaseSession, user: CurrentUser, country_code: str, code: str):
    """A third party answers this, so it is asked only for a country that declares one and only on behalf of an account."""
    country = await country_service.find_by_code(db, country_code)

    if country is None or country.postal_code_provider is None:
        raise NotFoundError()

    place = await postal_code.find(country.postal_code_provider, code)

    if place is None:
        raise NotFoundError("error.postal-code-not-found")

    return PostalAddressSchema(line1=place.line1, district=place.district, city=place.city, state=place.state)


router = build_router(country_service, CountrySchema, CountryCreate, CountryUpdate, "/countries", "countries")
