from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fastkit_core.api.envelope import build_message, success_envelope


class RolePermissions(BaseModel):
    permission_ids: list[int]


def build_role_router(
    runtime, security, manage_permission: str = "roles.manage"
) -> APIRouter:
    """Role editor endpoints backed by the permission service.

    ``security`` supplies ``get_current_user`` and ``authorize``; the consumer decides the
    permission that guards the editor.
    """

    router = APIRouter()
    permission_service = runtime.component("permission_service")

    async def _require(user):
        await security.authorize(user, manage_permission)

    @router.get("/meta/permissions")
    async def grouped_permissions(user=Depends(security.get_current_user)):
        await _require(user)

        return success_envelope(data=await permission_service.permissions_grouped())

    @router.get("/roles/{role_id}/permissions")
    async def role_permissions(role_id: int, user=Depends(security.get_current_user)):
        await _require(user)

        ids = await permission_service.role_permission_ids(role_id)

        return success_envelope(
            data={"permission_ids": [str(identifier) for identifier in ids]}
        )

    @router.put("/roles/{role_id}/permissions")
    async def set_role_permissions(
        role_id: int, payload: RolePermissions, user=Depends(security.get_current_user)
    ):
        await _require(user)

        await permission_service.set_role_permissions(role_id, payload.permission_ids)

        return success_envelope(
            message=build_message(
                "roles.permissions_updated", "Role permissions updated."
            )
        )

    return router
