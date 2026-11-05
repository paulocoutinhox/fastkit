from helpers.crud import build_readonly_router, build_router
from schemas.currency_create import CurrencyCreate
from schemas.currency_schema import CurrencySchema
from schemas.currency_update import CurrencyUpdate
from schemas.user_balance_schema import UserBalanceSchema
from services.currency_service import currency_service
from services.user_balance_service import user_balance_service

router = build_router(currency_service, CurrencySchema, CurrencyCreate, CurrencyUpdate, "/currencies", "currencies")
balance_router = build_readonly_router(user_balance_service, UserBalanceSchema, "/user-balances", "user balances")
