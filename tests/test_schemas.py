import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from models.account import Currency
from models.banner import Banner
from models.commerce import Product
from models.content import Content, ContentCategory
from models.gallery import Gallery, GalleryPhoto
from models.subscription import Plan
from schemas.account import CurrencyReference, CurrencySchema
from schemas.auth import AccountUpdateRequest, SignUpRequest
from schemas.banner import ActiveBannerSchema, BannerSchema
from schemas.commerce import AccountProductSchema, CatalogEntrySchema, CatalogProductSchema, ProductReference, ProductSchema, SiteProductSchema
from schemas.common import BaseSchema, as_optional
from schemas.content import ContentCategoryReference, ContentCategorySchema, ContentSchema
from schemas.gallery import GalleryPhotoSchema, GalleryReference, GallerySchema, PublicGalleryPhotoSchema, PublicGallerySchema
from schemas.subscription import CatalogPlanSchema, PlanReference, PlanSchema
from schemas.user import UserCreate


class Sample(BaseSchema):
    name: str
    size: int = 1


SampleUpdate = as_optional("SampleUpdate", Sample)


ADDRESSED = {
    Banner: (BannerSchema, ActiveBannerSchema),
    Currency: (CurrencyReference, CurrencySchema),
    Product: (ProductReference, ProductSchema, CatalogEntrySchema, CatalogProductSchema, SiteProductSchema, AccountProductSchema),
    ContentCategory: (ContentCategoryReference, ContentCategorySchema),
    Content: (ContentSchema,),
    Gallery: (GalleryReference, GallerySchema, PublicGallerySchema),
    GalleryPhoto: (GalleryPhotoSchema, PublicGalleryPhotoSchema),
    Plan: (PlanReference, PlanSchema, CatalogPlanSchema),
}


def test_the_map_above_is_every_model_a_client_addresses_and_not_the_ones_somebody_remembered():
    """A model that gains the mixin and no entry here would be covered by nothing, which is how a guard stops guarding."""
    import models.registry  # noqa: F401
    from helpers.db import Base
    from models.base import AddressedMixin

    carrying = {mapper.class_ for mapper in Base.registry.mappers if issubclass(mapper.class_, AddressedMixin)}

    assert carrying == set(ADDRESSED), f"the models a client addresses and the ones this guard names have drifted apart: {carrying ^ set(ADDRESSED)}"


def test_every_resource_a_client_addresses_carries_one_unique_uuid_through_every_answer():
    for model, schemas in ADDRESSED.items():
        unique = [constraint for constraint in model.__table__.constraints if isinstance(constraint, UniqueConstraint) and [column.name for column in constraint.columns] == ["uuid"]]

        assert "uuid" in model.__table__.columns, model.__name__
        assert [constraint.name for constraint in unique] == [f"{model.__tablename__}_uuid"], model.__name__
        assert all("uuid" in schema.model_fields for schema in schemas), model.__name__


def test_an_update_schema_makes_every_field_optional():
    assert SampleUpdate().model_dump(exclude_unset=True) == {}
    assert SampleUpdate(name="one").model_dump(exclude_unset=True) == {"name": "one"}


def test_an_update_schema_keeps_the_rules_of_its_base():
    with pytest.raises(ValidationError):
        SampleUpdate(size="big")


@pytest.mark.parametrize("payload", [{"cpf": None}, {"cpf": ""}])
def test_an_empty_cpf_is_stored_as_nothing(payload):
    request = SignUpRequest(username="newcomer", password="s3cret-password", email="newcomer@acme.com", **payload)

    assert request.cpf is None


def test_a_cpf_is_stored_without_punctuation():
    request = SignUpRequest(username="newcomer", password="s3cret-password", cpf="529.982.247-25")

    assert request.cpf == "52998224725"


def test_an_invalid_cpf_is_refused():
    with pytest.raises(ValidationError):
        SignUpRequest(username="newcomer", password="s3cret-password", cpf="12345678900")


def test_a_mobile_phone_is_stored_without_punctuation():
    request = SignUpRequest(username="newcomer", password="s3cret-password", mobile_phone="(11) 99999-8888")

    assert request.mobile_phone == "11999998888"


def test_a_mobile_phone_is_bounded_by_the_number_and_not_by_the_shape_it_was_written_in():
    """The shape a country writes a number in is punctuation the column never keeps, so what is measured is the number."""
    assert SignUpRequest(username="newcomer", password="s3cret-password", mobile_phone="+00 (00) 00000-0000").mobile_phone == "0000000000000"

    with pytest.raises(ValidationError):
        SignUpRequest(username="newcomer", password="s3cret-password", mobile_phone="9" * 17)


def test_an_empty_mobile_phone_is_stored_as_nothing():
    request = SignUpRequest(username="newcomer", password="s3cret-password", email="newcomer@acme.com", mobile_phone="")

    assert request.mobile_phone is None


def test_a_known_timezone_is_accepted():
    assert SignUpRequest(username="newcomer", password="s3cret-password", email="newcomer@acme.com", timezone="America/Sao_Paulo").timezone == "America/Sao_Paulo"


def test_an_unknown_timezone_is_refused():
    with pytest.raises(ValidationError):
        SignUpRequest(username="newcomer", password="s3cret-password", email="newcomer@acme.com", timezone="Mars/Olympus")


def test_the_account_update_leaves_an_empty_timezone_alone():
    assert AccountUpdateRequest().timezone is None
    assert AccountUpdateRequest(timezone=None).timezone is None


def test_the_account_update_checks_a_timezone_it_receives():
    with pytest.raises(ValidationError):
        AccountUpdateRequest(timezone="Mars/Olympus")

    assert AccountUpdateRequest(timezone="UTC").timezone == "UTC"


def test_the_account_update_normalizes_the_mobile_phone():
    assert AccountUpdateRequest(mobile_phone="(11) 99999-8888").mobile_phone == "11999998888"
    assert AccountUpdateRequest(mobile_phone="").mobile_phone is None


@pytest.mark.parametrize("payload,expected", [({"cpf": "529.982.247-25"}, "52998224725"), ({"cpf": ""}, None)])
def test_the_user_payload_normalizes_the_cpf(payload, expected):
    assert UserCreate(username="newcomer", password="s3cret-password", email="newcomer@acme.com", **payload).cpf == expected


def test_the_user_payload_refuses_an_invalid_cpf():
    with pytest.raises(ValidationError):
        UserCreate(username="newcomer", password="s3cret-password", cpf="12345678900")


def test_the_user_payload_normalizes_the_mobile_phone():
    assert UserCreate(username="newcomer", password="s3cret-password", mobile_phone="(11) 99999-8888").mobile_phone == "11999998888"


def test_the_user_payload_checks_the_timezone():
    with pytest.raises(ValidationError):
        UserCreate(username="newcomer", password="s3cret-password", email="newcomer@acme.com", timezone="Mars/Olympus")

    assert UserCreate(username="newcomer", password="s3cret-password", email="newcomer@acme.com", timezone="America/Sao_Paulo").timezone == "America/Sao_Paulo"
