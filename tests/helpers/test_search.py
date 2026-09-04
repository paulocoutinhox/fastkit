from sqlalchemy import Index
from sqlalchemy.dialects import mysql, postgresql, sqlite

from helpers.pagination import PageParams
from helpers.search import TextMatch, TextRank, phrase_of, search_index, tokens_of, words_of
from models.user import User
from services.commerce import product_service, purchase_service, user_product_service
from services.crud import CrudService
from services.user import user_service
from tests.factories import make_product, make_purchase

COLUMNS = (User.first_name, User.last_name)

DIALECTS = {"sqlite": sqlite.dialect(), "mysql": mysql.dialect(), "postgresql": postgresql.dialect()}


async def found(db, term: str) -> list[str]:
    _, items = await product_service.paginate(db, PageParams(search=term, limit=10, offset=0))

    return sorted(item.name for item in items)


async def people(db, term: str) -> list[str]:
    _, items = await user_service.paginate(db, PageParams(search=term, limit=10, offset=0))

    return sorted(item.first_name for item in items)


async def make_person(db, first_name: str, last_name: str):
    return await user_service.create(db, {"username": f"{first_name}.{last_name}".lower(), "email": f"{first_name}.{last_name}@acme.com".lower(), "password": "s3cret-password", "first_name": first_name, "last_name": last_name})


def rendered(element, dialect: str) -> str:
    return str(element.compile(dialect=DIALECTS[dialect], compile_kwargs={"literal_binds": True}))


def test_a_term_is_the_words_it_carries():
    assert tokens_of("machado assis") == ["machado", "assis"]


def test_the_operators_of_every_dialect_are_stripped_from_the_term():
    assert words_of("+alien* -ista @x") == ["alien", "ista", "x"]


def test_a_term_of_only_operators_reaches_no_word():
    assert tokens_of("*+-") == []


def test_the_wildcards_of_like_never_survive_into_a_pattern():
    assert words_of("100% _de_ desconto") == ["100", "de", "desconto"]


def test_a_word_the_index_cannot_hold_is_never_required():
    """InnoDB indexes nothing below three characters, and asking for `+de*` answers no row at all."""
    assert tokens_of("machado de assis") == ["machado", "assis"]
    assert phrase_of("machado de assis") == "machado de assis"


def test_a_phrase_is_the_words_put_back_in_order():
    assert phrase_of("  machado   assis ") == "machado assis"


def test_mysql_asks_for_every_word_by_prefix():
    """The truncation is what keeps a short word searchable, because InnoDB drops neither a stopword nor a token below its minimum when one is asked for by prefix."""
    sql = rendered(TextMatch(COLUMNS, ["machado", "assis"]), "mysql")

    assert sql == "MATCH (user.first_name, user.last_name) AGAINST ('+machado* +assis*' IN BOOLEAN MODE)"


def test_postgresql_asks_the_same_question_of_its_own_index():
    sql = rendered(TextMatch(COLUMNS, ["machado", "assis"]), "postgresql")

    assert "to_tsquery('simple', 'machado:* & assis:*')" in sql
    assert "to_tsvector('simple'" in sql


def test_sqlite_answers_the_same_words_by_reading_the_columns_as_one_document():
    sql = rendered(TextMatch(COLUMNS, ["machado"]), "sqlite")

    assert "LIKE lower('machado%')" in sql
    assert "LIKE lower('% machado%')" in sql
    assert "coalesce(user.first_name, '') || ' ' || coalesce(user.last_name, '')" in sql


def test_every_dialect_ranks_the_phrase_as_it_was_typed():
    assert rendered(TextRank(COLUMNS, "machado assis"), "mysql") == "MATCH (user.first_name, user.last_name) AGAINST ('\"machado assis\"' IN BOOLEAN MODE)"
    assert "phraseto_tsquery('simple', 'machado assis')" in rendered(TextRank(COLUMNS, "machado assis"), "postgresql")
    assert "LIKE lower('%machado assis%')" in rendered(TextRank(COLUMNS, "machado assis"), "sqlite")


def test_a_search_index_is_a_fulltext_index_where_the_dialect_has_one():
    index = search_index("commerce_product_search", "name")

    assert isinstance(index, Index)
    assert index.dialect_options["mysql"]["prefix"] == "FULLTEXT"


def test_a_service_reading_prose_is_answered_by_an_index_covering_exactly_it():
    """MySQL refuses a match against columns no fulltext index covers, so declaring one without the other is a query that only fails in production."""
    for service in CrudService.__subclasses__():
        if not service.text_search_fields:
            continue

        table = service.model.__table__
        covering = [index for index in table.indexes if index.dialect_options["mysql"]["prefix"] == "FULLTEXT"]
        columns = [tuple(column.name for column in index.columns) for index in covering]

        assert tuple(service.text_search_fields) in columns, f"{service.__name__}: {table.name} has no fulltext index over {service.text_search_fields}"


def test_prose_is_searched_by_word_and_an_identifier_by_any_piece_of_itself():
    statement = product_service.apply_search(product_service.base_statement(), "  hand ")
    sql = rendered(statement, "mysql")

    assert "AGAINST ('+hand*' IN BOOLEAN MODE)" in sql
    assert "lower(commerce_product.slug) LIKE lower('%%hand%%')" in sql


def test_a_term_of_only_operators_still_reaches_the_identifier():
    statement = product_service.apply_search(product_service.base_statement(), "*")
    sql = rendered(statement, "mysql")

    assert "lower(commerce_product.slug) LIKE lower('%%*%%')" in sql
    assert "AGAINST" not in sql


def test_a_match_is_never_compared_against_a_boolean_the_dialect_invented():
    """MySQL has no native boolean and would read a relevance score as a truth value, and in boolean mode that score is not 1."""
    statement = product_service.apply_search(product_service.base_statement(), "handbook")

    assert "IN BOOLEAN MODE) = 1" not in rendered(statement, "mysql")


def test_an_order_the_client_asked_for_outranks_the_relevance_of_a_search():
    assert product_service.search_ordering("handbook", "-createdAt") == []
    assert product_service.search_ordering("handbook", None) != []


def test_a_service_with_no_prose_never_ranks():
    assert product_service.search_ordering("", None) == []


async def test_a_word_is_reached_from_its_start_and_never_from_its_middle(db):
    await make_product(db, name="The Handbook", slug="hb-one")

    assert await found(db, "hand") == ["The Handbook"]
    assert await found(db, "Handbook") == ["The Handbook"]
    assert await found(db, "andboo") == []


async def test_every_word_of_a_term_has_to_be_reached(db):
    await make_product(db, name="Starter pack")
    await make_product(db, name="Starter guide")

    assert await found(db, "starter") == ["Starter guide", "Starter pack"]
    assert await found(db, "guide starter") == ["Starter guide"]


async def test_a_term_spread_across_two_columns_still_answers(db):
    await make_person(db, "Machado", "Assis")

    assert await people(db, "machado assis") == ["Machado"]


async def test_the_phrase_as_it_was_typed_comes_before_the_words_it_was_cut_into(db):
    await make_person(db, "Assis", "Machado")
    await make_person(db, "Machado", "Assis")

    page = PageParams(search="machado assis", limit=10, offset=0)
    _, items = await user_service.paginate(db, page)

    assert [item.first_name for item in items] == ["Machado", "Assis"]


def test_a_resource_that_declares_no_search_ignores_the_term_instead_of_answering_nothing():
    statement = user_product_service.base_statement()

    assert user_product_service.apply_search(statement, "anything") is statement


async def test_a_wildcard_somebody_typed_matches_itself(db, tenant, member):
    """Searching for `%` used to answer every row, which reads as a search that found everything."""
    product = await make_product(db, tenant)

    await make_purchase(db, tenant, member, product, external_id="9781234567897")
    await make_purchase(db, tenant, member, product, external_id="50%-off-2026")

    _, items = await purchase_service.paginate(db, PageParams(search="50%", limit=10, offset=0))

    assert [item.external_id for item in items] == ["50%-off-2026"]
