from helpers.crud import build_readonly_router, build_router
from schemas.account import CurrencyCreate, CurrencySchema, CurrencyUpdate, UserBalanceSchema
from services.account import currency_service, user_balance_service

router = build_router(currency_service, CurrencySchema, CurrencyCreate, CurrencyUpdate, "/currencies", "currencies")
balance_router = build_readonly_router(user_balance_service, UserBalanceSchema, "/user-balances", "user balances")
