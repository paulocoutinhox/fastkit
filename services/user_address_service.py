from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from enums.user_address_type import UserAddressType
from helpers.validation_error import ValidationError
from models.user import User
from models.user_address import UserAddress
from services.country_service import country_service
from services.crud_service import CrudService
from services.reach import Reach
from services.user_service import user_service


class UserAddressService(CrudService):
    model = UserAddress
    reaches_through = Reach(UserAddress.user_id, User)
    search_fields = ("postal_code", "city")
    filter_fields = ("user_id", "type", "country_code")
    ordering_fields = ("id", "type", "city", "created_at")
    default_ordering = "-id"
    relations = ("user",)
    label_fields = ("line1",)

    async def prepare(self, data: dict, instance) -> dict:
        prepared = dict(data)

        if prepared.get("country_code"):
            prepared["country_code"] = prepared["country_code"].upper()

        return prepared

    async def validate(self, db: AsyncSession, data: dict, instance) -> None:
        prepared = await self.prepare(data, instance)
        user_id = self.declared(prepared, instance, "user_id")
        address_type = self.declared(prepared, instance, "type")

        await user_service.hold(db, user_id)
        country_code = self.declared(prepared, instance, "country_code")

        await self.ensure_unique(db, UserAddress.type, address_type, "error.address-type-already-used", "type", instance, UserAddress.user_id == user_id)

        # The code is a natural key of the registry, so an address is only ever written in a country this instance offers.
        if country_code and await country_service.find_by_code(db, country_code) is None:
            raise ValidationError("error.country-not-offered", "country_code")

    async def find_for_user(self, db: AsyncSession, user_id: int, address_type: UserAddressType) -> UserAddress | None:
        return await db.scalar(select(UserAddress).where(UserAddress.user_id == user_id, UserAddress.type == address_type))

    async def save_for_user(self, db: AsyncSession, user_id: int, address_type: UserAddressType, data: dict) -> UserAddress:
        """One address per purpose, so the account writes the same row again instead of collecting a second one."""
        existing = await self.find_for_user(db, user_id, address_type)

        if existing is not None:
            return await self.update(db, existing.id, data)

        return await self.create(db, {**data, "user_id": user_id, "type": address_type})

    async def list_for_user(self, db: AsyncSession, user_id: int) -> list[UserAddress]:
        result = await db.execute(self.base_statement().where(UserAddress.user_id == user_id).order_by(UserAddress.type.asc()))

        return list(result.scalars().unique())


user_address_service = UserAddressService()
