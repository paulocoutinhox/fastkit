from fastkit_db.repository import Repository
from fastkit_tenancy.models import Tenant


class TenantRepository(Repository[Tenant]):
    def __init__(self, session):
        super().__init__(Tenant, session)
