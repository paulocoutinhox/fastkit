from models.benefit import Benefit
from models.entitlement import Entitlement
from models.plan_entitlement import PlanEntitlement
from services.crud_service import CrudService
from services.dependent import Dependent


class EntitlementService(CrudService):
    model = Entitlement
    shared = True
    markup_fields = ("description",)
    search_fields = ()
    text_search_fields = ("name",)
    filter_fields = ("tenant_id", "active")
    ordering_fields = ("id", "name", "created_at")
    default_ordering = "name"
    relations = ("tenant",)
    label_fields = ("name",)
    dependents = (Dependent(Benefit, "entitlement_id"), Dependent(PlanEntitlement, "entitlement_id"))


entitlement_service = EntitlementService()
