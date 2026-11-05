from schemas.common import as_optional
from schemas.entitlement_create import EntitlementCreate

EntitlementUpdate = as_optional("EntitlementUpdate", EntitlementCreate)
