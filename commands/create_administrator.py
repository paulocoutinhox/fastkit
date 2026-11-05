from pydantic import ValidationError

from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.base_command import BaseCommand
from helpers.command_error import CommandError
from helpers.db import AsyncSessionLocal
from helpers.errors import field_path, validation_message
from helpers.schema import create_schema
from schemas.user_create import UserCreate
from services.seed_service import ADMIN
from services.user_service import user_service


class Command(BaseCommand):
    help = "Create an account able to sign in to the admin, outside every tenant."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=ADMIN["username"])
        parser.add_argument("--email", default=ADMIN["email"])

        # A password written here opens the whole panel, so none is assumed, and one the API would refuse is refused here too.
        parser.add_argument("--password", required=True)

    async def handle(self, username: str, email: str, password: str, **options):
        try:
            payload = UserCreate.model_validate({"username": username, "email": email, "password": password, "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE})
        except ValidationError as refused:
            raise CommandError(", ".join(f"{field_path(error['loc'])}: {validation_message(error)}" for error in refused.errors())) from refused

        await create_schema()

        # An administrator is global, because that is the scope the admin sign in resolves in.
        async with AsyncSessionLocal() as session:
            user = await user_service.create(session, payload.model_dump(exclude_unset=True) | {"tenant_id": None})

        self.stdout.write(f"administrator created with id {user.id}", self.style.SUCCESS)
