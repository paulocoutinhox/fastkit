from fastapi import APIRouter, Depends, File, UploadFile

from fastkit_core.api.envelope import build_message, success_envelope
from fastkit_core.errors.codes import VALIDATION_FAILED
from fastkit_core.errors.exceptions import FieldError, ValidationError
from fastkit_admin.api import AdminDeps
from fastkit_admin.helpers import DEFAULT_MAX_UPLOAD_BYTES, read_upload
from fastkit_admin.profile.identifier_create import IdentifierCreate
from fastkit_admin.profile.password_change import PasswordChange
from fastkit_admin.profile.summary import profile_summary
from fastkit_admin.profile.update import ProfileUpdate


def build_profile_router(
    deps: AdminDeps,
    account_service,
    password_service,
    upload_avatar=None,
    avatar_url=None,
    files=None,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    avatar_owner_type: str = "user",
    avatar_slot: str = "avatar",
) -> APIRouter:
    """Self-service profile management for the signed-in user, decoupled from storage via an upload handler.

    The avatar file reference is keyed by ``avatar_owner_type``/``avatar_slot`` so a consumer that
    tracks stored-file references under a different owner scheme can override the pair.
    """

    router = APIRouter()

    async def _load(user):
        identifiers = await account_service.list_identifiers(user.id)
        file_id = user.profile.avatar_file_id if user.profile else None
        url = (
            await avatar_url(file_id) if (avatar_url is not None and file_id) else None
        )

        return profile_summary(
            user, identifiers, account_service.identifier_types(), url
        )

    async def _audit(action, user):
        if deps.audit is not None:
            await deps.audit(action, "profile", str(user.id))

    @router.get("/profile")
    async def get_profile(user=Depends(deps.get_current_user)):
        return success_envelope(data=await _load(user))

    @router.put("/profile")
    async def update_profile(
        payload: ProfileUpdate, user=Depends(deps.get_current_user)
    ):
        updated = await account_service.update_profile(user.id, **payload.model_dump())
        await _audit("profile_update", user)

        return success_envelope(
            data=await _load(updated),
            message=build_message("profile.updated", "Profile updated."),
        )

    @router.post("/profile/password")
    async def change_password(
        payload: PasswordChange, user=Depends(deps.get_current_user)
    ):
        if not password_service.verify(
            user.password_hash or "", payload.current_password
        ):
            raise ValidationError(
                VALIDATION_FAILED,
                message="current password is incorrect",
                field_errors=[
                    FieldError("current_password", "validation.password-incorrect")
                ],
            )

        await account_service.set_password_hash(
            user.id, password_service.hash(payload.new_password)
        )
        await _audit("password_change", user)

        return success_envelope(
            message=build_message("profile.password_changed", "Password changed.")
        )

    @router.post("/profile/identifiers")
    async def add_identifier(
        payload: IdentifierCreate, user=Depends(deps.get_current_user)
    ):
        if payload.type not in account_service.identifier_types():
            raise ValidationError(
                VALIDATION_FAILED,
                message=f"'{payload.type}' is not a valid login method type",
                field_errors=[FieldError("type", "validation.identifier-type")],
            )

        await account_service.add_identifier(
            user.id, _tenant_of(user), payload.type, payload.value
        )
        await _audit("identifier_add", user)

        return success_envelope(
            data=await _load(user),
            message=build_message("profile.identifier_added", "Login method added."),
        )

    @router.delete("/profile/identifiers/{identifier_id}")
    async def remove_identifier(
        identifier_id: str, user=Depends(deps.get_current_user)
    ):
        await account_service.remove_identifier(user.id, identifier_id)
        await _audit("identifier_remove", user)

        return success_envelope(
            data=await _load(user),
            message=build_message(
                "profile.identifier_removed", "Login method removed."
            ),
        )

    @router.post("/profile/avatar")
    async def upload_profile_avatar(
        file: UploadFile = File(...), user=Depends(deps.get_current_user)
    ):
        data = await read_upload(file, max_bytes)
        result = await upload_avatar(data, file.filename, file.content_type)
        await account_service.update_profile(user.id, avatar_file_id=result["file_id"])

        if files is not None:
            await files.link(avatar_owner_type, user.id, avatar_slot, result["file_id"])

        return success_envelope(
            data={"url": result["url"], "file_id": str(result["file_id"])},
            message=build_message("profile.avatar_updated", "Avatar updated."),
        )

    return router


def _tenant_of(user) -> int:
    return 0 if user.tenant_id is None else user.tenant_id
