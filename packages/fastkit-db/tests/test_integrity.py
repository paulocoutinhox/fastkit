from fastkit_db.integrity import classify_integrity_error


class _Wrapped:
    def __init__(self, orig):
        self.orig = orig


def _classify(text):
    return classify_integrity_error(_Wrapped(text))


def test_unique_sqlite_single_and_composite():
    single = _classify("UNIQUE constraint failed: demo_tag.slug")
    composite = _classify(
        "UNIQUE constraint failed: plan_entitlement.plan_id, plan_entitlement.entitlement_id"
    )

    assert single.kind == "unique"
    assert single.columns == ["slug"]
    assert composite.columns == ["plan_id", "entitlement_id"]


def test_unique_postgres():
    error = _classify(
        'duplicate key value violates unique constraint "uq_x"\nDETAIL:  Key (email)=(a@b.com) already exists.'
    )

    assert error.kind == "unique"
    assert error.columns == ["email"]


def test_foreign_key_sqlite_without_column_and_postgres_with_column():
    sqlite = _classify("FOREIGN KEY constraint failed")
    postgres = _classify(
        'insert or update on table "demo_product" violates foreign key constraint "fk"\nDETAIL:  Key (category_id)=(99) is not present in table "demo_category".'
    )

    assert sqlite.kind == "foreign_key"
    assert sqlite.columns == []
    assert postgres.kind == "foreign_key"
    assert postgres.columns == ["category_id"]


def test_not_null_sqlite_and_postgres():
    sqlite = _classify("NOT NULL constraint failed: demo_product.name")
    postgres = _classify(
        'null value in column "name" of relation "demo_product" violates not-null constraint'
    )

    assert sqlite.kind == "not_null"
    assert sqlite.columns == ["name"]
    assert postgres.kind == "not_null"
    assert postgres.columns == ["name"]


def test_check_and_unknown():
    assert _classify("CHECK constraint failed: price_positive").kind == "check"
    assert _classify('new row violates check constraint "c"').kind == "check"
    assert _classify("some unrelated database error").kind == "unknown"
