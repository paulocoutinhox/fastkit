from schemas.common import as_optional
from schemas.currency_create import CurrencyCreate

CurrencyUpdate = as_optional("CurrencyUpdate", CurrencyCreate)
