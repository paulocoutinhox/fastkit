from fastapi import APIRouter, Depends, status

from helpers import audit
from helpers.auth import AdministratorUser, get_administrator
from helpers.crud import build_readonly_router
from helpers.db import DatabaseSession
from schemas.account import CreditTransactionCreate, CreditTransactionSchema
from services.account import credit_transaction_service

router = build_readonly_router(credit_transaction_service, CreditTransactionSchema, "/credit-transactions", "credit transactions")

write_router = APIRouter(prefix="/credit-transactions", tags=["credit transactions"], dependencies=[Depends(get_administrator)])


@write_router.post("", response_model=CreditTransactionSchema, status_code=status.HTTP_201_CREATED, summary="Move a balance by hand")
async def create_transaction(db: DatabaseSession, administrator: AdministratorUser, payload: CreditTransactionCreate):
    """The ledger is append only, so an entry is added to correct a balance and never edited or removed."""
    entry = await credit_transaction_service.create(db, payload.model_dump())
    await audit.written(db, administrator, "moved a balance", "credit-transactions", entry.id)

    return CreditTransactionSchema.model_validate(entry)
