from schemas.common import as_optional
from schemas.plan_entitlement_create import PlanEntitlementCreate

PlanEntitlementUpdate = as_optional("PlanEntitlementUpdate", PlanEntitlementCreate)
