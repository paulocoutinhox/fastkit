from fastapi import APIRouter, Depends

from fastkit_core.api.envelope import build_message, success_envelope
from fastkit_accounts.models import User
from fastkit_admin.security import AdminSecurity


def build_gdpr_router(runtime, security: AdminSecurity) -> APIRouter:
    """LGPD/GDPR endpoints: the signed-in user can export or erase their own data."""

    router = APIRouter()
    database = runtime.component("database")
    audit = runtime.component("audit_log_service")

    @router.get("/gdpr/export")
    async def export_data(user=Depends(security.get_current_user)):
        payload = {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "preferred_locale": user.preferred_locale,
            "timezone": user.timezone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

        await audit.record("update", "User", resource_id=str(user.id), after={"action": "gdpr_export"})

        return success_envelope(data=payload)

    @router.post("/gdpr/delete")
    async def erase_data(user=Depends(security.get_current_user)):
        async with database.session_factory() as session:
            stored = await session.get(User, user.id)
            stored.is_active = False
            stored.email = None
            stored.username = None
            stored.phone = None
            stored.first_name = None
            stored.last_name = None
            stored.display_name = "Deleted user"

            for identifier in list(stored.identifiers):
                await session.delete(identifier)

            await session.commit()

        await audit.record("delete", "User", resource_id=str(user.id), before={"action": "gdpr_erase"})

        return success_envelope(message=build_message("gdpr.erased", "Your personal data has been erased."))

    return router
