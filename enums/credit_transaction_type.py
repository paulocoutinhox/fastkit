from enum import StrEnum


class CreditTransactionType(StrEnum):
    CREDIT = "credit"
    DEBIT = "debit"
    REVERSAL = "reversal"
    ADJUSTMENT = "adjustment"
