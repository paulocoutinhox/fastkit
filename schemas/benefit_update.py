from schemas.benefit_create import BenefitCreate
from schemas.common import as_optional

BenefitUpdate = as_optional("BenefitUpdate", BenefitCreate)
