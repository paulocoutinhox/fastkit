from schemas.common import as_optional
from schemas.plan_create import PlanCreate

PlanUpdate = as_optional("PlanUpdate", PlanCreate)
