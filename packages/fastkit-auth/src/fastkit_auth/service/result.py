from dataclasses import dataclass

from fastkit_accounts.models import User
from fastkit_auth.models import Session


@dataclass(frozen=True)
class LoginResult:
    user: User
    session: Session
    token: str
    session_token: str
    effective_tenant_id: int
