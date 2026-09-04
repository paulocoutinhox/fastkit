import pytest

from enums.account import CreditTransactionType
from helpers.errors import ValidationError
from models.base import BIG_INTEGER_MAX
from services.account import credit_transaction_service
from tests.factories import make_currency, make_entitlement


async def balance_of(db, user, currency) -> int:
    """What the account holds of one currency, read from the balance the ledger of that currency explains."""
    from services.account import user_balance_service

    held = await user_balance_service.list_for_user(db, user.id)

    return next((row.amount for row in held if row.currency_id == currency.id), 0)


async def test_credit_moves_the_wallet_and_writes_the_ledger(client, db, member, admin_headers, currency):
    payload = {"userId": member.id, "currencyId": currency.id, "type": CreditTransactionType.CREDIT, "amount": 25}

    response = await client.post("/api/credit-transactions", json=payload, headers=admin_headers)

    assert response.status_code == 201
    assert response.json()["balanceAfter"] == 25

    await db.refresh(member)

    assert await balance_of(db, member, currency) == 25


async def test_debit_is_stored_negative(client, db, member, admin_headers, currency):
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 30, None, "key-1", None, {})

    payload = {"userId": member.id, "currencyId": currency.id, "type": CreditTransactionType.DEBIT, "amount": 10}
    response = await client.post("/api/credit-transactions", json=payload, headers=admin_headers)

    assert response.json()["amount"] == -10
    assert response.json()["balanceAfter"] == 20


async def test_debit_below_zero_is_refused(client, member, admin_headers, currency):
    payload = {"userId": member.id, "currencyId": currency.id, "type": CreditTransactionType.DEBIT, "amount": 10}

    response = await client.post("/api/credit-transactions", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.insufficient-credits"


async def test_an_unknown_user_is_refused(client, admin_headers, currency):
    payload = {"user_id": 999999, "currencyId": currency.id, "type": CreditTransactionType.CREDIT, "amount": 5}

    response = await client.post("/api/credit-transactions", json=payload, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.related-not-found"


async def test_the_same_idempotency_key_moves_the_wallet_once(db, member, currency):
    first = await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 5, None, "key-1", None, {})
    second = await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 5, None, "key-1", None, {})

    await db.refresh(member)

    assert first.id == second.id
    assert await balance_of(db, member, currency) == 5


async def test_the_ledger_is_append_only(client, db, member, admin_headers, currency):
    """A balance is corrected with another movement, so there is no address at all for editing one that was written."""
    entry = await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 5, None, "key-1", None, {})

    edited = await client.put(f"/api/credit-transactions/{entry.id}", json={"amount": 100}, headers=admin_headers)
    removed = await client.delete(f"/api/credit-transactions/{entry.id}", headers=admin_headers)

    assert edited.status_code == 405
    assert removed.status_code == 405


async def test_filter_by_currency(client, db, member, admin_headers, currency):
    other = await make_currency(db, code="gem", name="Gems")

    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 5, None, "key-1", None, {})
    await credit_transaction_service.move(db, member.id, other.id, CreditTransactionType.CREDIT, 5, None, "key-2", None, {})

    assert (await client.get(f"/api/credit-transactions?currencyId={currency.id}", headers=admin_headers)).json()["count"] == 1
    assert (await client.get(f"/api/credit-transactions?currencyId={other.id}", headers=admin_headers)).json()["count"] == 1


async def test_an_entry_of_the_ledger_is_never_edited(client, db, member, admin_headers, currency):
    """The running total in `balance_after` is what a line explains, and rewriting an entry makes every one after it a lie."""
    created = await client.post("/api/credit-transactions", json={"userId": member.id, "currencyId": currency.id, "type": "credit", "amount": 5}, headers=admin_headers)

    assert (await client.put(f"/api/credit-transactions/{created.json()['id']}", json={"amount": 500}, headers=admin_headers)).status_code == 405
    assert (await client.delete(f"/api/credit-transactions/{created.json()['id']}", headers=admin_headers)).status_code == 405


@pytest.mark.parametrize("transaction_type,sent,stored", [("credit", 100, 100), ("debit", 20, -20), ("reversal", 50, -50), ("adjustment", 30, 30), ("adjustment", -30, -30)])
async def test_the_type_decides_the_direction_and_only_an_adjustment_carries_its_own(client, db, member, admin_headers, currency, transaction_type, sent, stored):
    """The type is what an audit reads, so a movement named credit must never be one that took from the balance."""
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 1000, None, "opening", None, {})

    response = await client.post("/api/credit-transactions", json={"userId": member.id, "currencyId": currency.id, "type": transaction_type, "amount": sent}, headers=admin_headers)

    assert response.json()["amount"] == stored
    assert response.json()["balanceAfter"] == 1000 + stored


@pytest.mark.parametrize("transaction_type", ["credit", "debit", "reversal"])
async def test_a_directed_movement_refuses_a_negative_magnitude_instead_of_reading_it_backwards(client, db, member, admin_headers, currency, transaction_type):
    """A minus sign used to be dropped, so an operator who typed minus fifty on a credit watched fifty land in the balance."""
    response = await client.post("/api/credit-transactions", json={"userId": member.id, "currencyId": currency.id, "type": transaction_type, "amount": -50}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.amount-must-be-positive"


async def test_a_movement_no_column_could_hold_is_refused_before_it_reaches_the_driver(client, member, admin_headers, currency):
    """A number past what the column holds overflowed inside the driver and answered a five hundred."""
    response = await client.post("/api/credit-transactions", json={"userId": member.id, "currencyId": currency.id, "type": "credit", "amount": 10**30}, headers=admin_headers)

    assert response.status_code == 422


async def test_a_balance_that_would_not_fit_the_column_is_refused_like_one_below_zero(db, member, currency):
    """The floor was guarded and the ceiling was not, so the entry that broke it reached the driver."""
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, BIG_INTEGER_MAX, None, "nearly-all", None, {})

    with pytest.raises(ValidationError) as refused:
        await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 1, None, "one-too-many", None, {})

    assert refused.value.code == "error.balance-out-of-range"


async def test_a_currency_is_named_by_the_tenant_that_added_it(client, db, tenant, admin_headers):
    """A currency belongs to whoever added it, and two tenants naming theirs the same is two currencies."""
    mine = await client.post("/api/currencies", json={"name": "Coins", "tenantId": tenant.id}, headers=admin_headers)

    assert mine.status_code == 201
    assert mine.json()["code"] == "coins"

    assert (await client.post("/api/currencies", json={"name": "Coins", "tenantId": tenant.id}, headers=admin_headers)).status_code == 409
    assert (await client.post("/api/currencies", json={"name": "Coins"}, headers=admin_headers)).status_code == 201


async def test_a_movement_names_a_currency_that_exists(client, member, admin_headers):
    answer = await client.post("/api/credit-transactions", json={"userId": member.id, "currencyId": 999, "type": "credit", "amount": 5}, headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["errors"] == {"currencyId": "The related record was not found."}


async def test_a_movement_names_an_account_that_exists(client, currency, admin_headers):
    answer = await client.post("/api/credit-transactions", json={"userId": 999, "currencyId": currency.id, "type": "credit", "amount": 5}, headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["errors"] == {"userId": "The related record was not found."}


async def test_only_a_credit_benefit_names_a_currency(client, db, tenant, currency, admin_headers):
    """A currency on an access benefit says nothing, and a benefit saying nothing is one nobody can read."""
    entitlement = await make_entitlement(db, tenant)
    payload = {"entitlementId": entitlement.id, "type": "access", "target": "member", "quantity": 1, "cadence": "on_activation", "currencyId": currency.id}

    answer = await client.post("/api/benefits", json=payload, headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.benefit-currency-only-on-a-credit-benefit"


async def test_the_site_is_offered_the_currencies_its_tenant_reaches(db, tenant):
    from services.account import currency_service

    shared = await make_currency(db)
    theirs = await make_currency(db, tenant, code="house", name="House points")
    await make_currency(db, code="hidden", name="Hidden", active=False)

    reachable = await currency_service.list_reachable(db, tenant.id)

    assert {row.id for row in reachable} == {shared.id, theirs.id}
