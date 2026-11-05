from enums.upload_purpose import UploadPurpose
from enums.user_role import UserRole
from services.crud_service import services_by_model


def roles_storing(purpose: UploadPurpose) -> set[UserRole]:
    """Who may put a file of this purpose into storage, which is whoever may write a record that keeps one: a file column of that purpose, or markup, where the editor embeds an image."""
    return {role for service in services_by_model().values() if purpose in service.file_fields.values() or (purpose == UploadPurpose.IMAGE and service.markup_fields) for role in service.roles}


# What keeps the pages of the site current, which is the one thing a role short of an administrator is given here.
EDITING = (UserRole.ADMINISTRATOR, UserRole.EDITOR)
