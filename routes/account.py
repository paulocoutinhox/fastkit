from fastapi import APIRouter, File, Response, UploadFile, status

from enums.user import UserAddressType
from helpers.auth import CurrentBrand, CurrentUser
from helpers.db import DatabaseSession
from helpers.pagination import ListingLimit, ListingOffset, Page
from helpers.security import create_token
from schemas.account import AccountBalanceListResponse, AccountBalanceSchema, AccountCreditSchema
from schemas.auth import AccountUpdateRequest, PasswordChangeRequest, PasswordResetConfirmRequest, PasswordResetRequest, TokenResponse
from schemas.common import BaseSchema
from schemas.subscription import AccountEntitlementSchema, AccountSubscriptionListResponse, AccountSubscriptionSchema
from schemas.user import AccountAddressListResponse, AccountAddressRequest, AccountAddressSchema, AccountSchema
from services.account import credit_transaction_service, user_balance_service
from services.auth import auth_service
from services.reconciliation import reconciliation_service
from services.subscription import subscription_service, user_entitlement_service
from services.user import user_address_service, user_service

router = APIRouter(prefix="/account", tags=["account"])


class AccountEntitlementListResponse(BaseSchema):
    items: list[AccountEntitlementSchema]


@router.get("/me", response_model=AccountSchema, summary="Read the signed in account")
async def read_me(db: DatabaseSession, user: CurrentUser):
    return AccountSchema.model_validate(await user_service.present(user))


@router.put("/me", response_model=AccountSchema, summary="Update the signed in account")
async def update_me(db: DatabaseSession, user: CurrentUser, payload: AccountUpdateRequest):
    updated = await user_service.update(db, user.id, payload.model_dump(exclude_unset=True))

    return AccountSchema.model_validate(await user_service.present(updated))


@router.post("/avatar", response_model=AccountSchema, summary="Send the picture of the signed in account")
async def send_avatar(db: DatabaseSession, user: CurrentUser, file: UploadFile = File(...)):
    """One call: the image is stored under the avatar rule and the account already answers with the address of it."""
    return AccountSchema.model_validate(await user_service.present(await user_service.settle_avatar(db, user, file)))


@router.delete("/avatar", response_model=AccountSchema, summary="Remove the picture of the signed in account")
async def remove_avatar(db: DatabaseSession, user: CurrentUser):
    return AccountSchema.model_validate(await user_service.present(await user_service.discard_avatar(db, user)))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Erase the signed in account")
async def erase_me(db: DatabaseSession, user: CurrentUser):
    await user_service.erase(db, user)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password", response_model=TokenResponse, summary="Change the password")
async def change_password(db: DatabaseSession, user: CurrentUser, payload: PasswordChangeRequest):
    """Every other session ends here, and this one is handed the token that replaces the one it arrived with."""
    await auth_service.change_password(db, user, payload.current_password, payload.new_password)

    return TokenResponse(token=create_token(user.token, user.role, user.session_epoch), user=AccountSchema.model_validate(await user_service.present(user)))


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT, summary="Start a password reset")
async def start_password_reset(db: DatabaseSession, brand: CurrentBrand, payload: PasswordResetRequest):
    """An unknown login answers exactly like a known one, so the endpoint never confirms who has an account here."""
    await auth_service.start_password_reset(db, brand, payload.login)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT, summary="Confirm a password reset")
async def confirm_password_reset(db: DatabaseSession, payload: PasswordResetConfirmRequest):
    await auth_service.confirm_password_reset(db, payload.token, payload.new_password)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/entitlements", response_model=AccountEntitlementListResponse, summary="List what the signed in account is entitled to")
async def list_entitlements(db: DatabaseSession, user: CurrentUser):
    items = await user_entitlement_service.list_for_user(db, user.id)

    return AccountEntitlementListResponse(items=[AccountEntitlementSchema(code=item.entitlement.code, name=item.entitlement.name, status=item.status, started_at=item.started_at, expires_at=item.expires_at) for item in items])


@router.get("/balances", response_model=AccountBalanceListResponse, summary="List what the signed in account holds of each currency")
async def list_balances(db: DatabaseSession, user: CurrentUser):
    held = await user_balance_service.list_for_user(db, user.id)

    return AccountBalanceListResponse(items=[AccountBalanceSchema(currency=row.currency, amount=row.amount) for row in held])


@router.get("/credits", response_model=Page[AccountCreditSchema], summary="List the credit ledger")
async def list_credits(db: DatabaseSession, user: CurrentUser, limit: ListingLimit = 50, offset: ListingOffset = 0):
    total, items = await credit_transaction_service.list_for_user(db, user.id, limit, offset)

    return Page[AccountCreditSchema](count=total, limit=limit, offset=offset, items=[AccountCreditSchema.model_validate(item) for item in items])


@router.post("/subscriptions/refresh", response_model=AccountSubscriptionListResponse, summary="Read what the store holds for this account right now")
async def refresh_subscriptions(db: DatabaseSession, user: CurrentUser):
    """The app calls this the moment a purchase goes through, so what it shows next never waits for a webhook."""
    await reconciliation_service.refresh(db, user)

    return AccountSubscriptionListResponse(items=[AccountSubscriptionSchema.model_validate(item) for item in await subscription_service.list_for_user(db, user.id)])


@router.get("/addresses", response_model=AccountAddressListResponse, summary="List the addresses of the signed in account")
async def list_addresses(db: DatabaseSession, user: CurrentUser):
    items = await user_address_service.list_for_user(db, user.id)

    return AccountAddressListResponse(items=[AccountAddressSchema.model_validate(item) for item in items])


@router.put("/addresses/{address_type}", response_model=AccountAddressSchema, summary="Write the address of one purpose")
async def save_address(db: DatabaseSession, user: CurrentUser, address_type: UserAddressType, payload: AccountAddressRequest):
    """One address per purpose, so writing it again replaces the row instead of collecting a second one."""
    address = await user_address_service.save_for_user(db, user.id, address_type, payload.model_dump())

    return AccountAddressSchema.model_validate(address)


@router.delete("/addresses/{address_type}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove the address of one purpose")
async def remove_address(db: DatabaseSession, user: CurrentUser, address_type: UserAddressType):
    address = await user_address_service.find_for_user(db, user.id, address_type)

    if address is not None:
        await user_address_service.delete(db, address.id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
