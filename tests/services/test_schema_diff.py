"""What the proposal writes for a change that keeps a name, which is where a straight addition collides or doubles."""

from services.schema_diff import statements_for


def shapes(indexes=None, keys=None) -> dict:
    empty = {"missing": [], "extra": []}

    return {"tables": empty, "columns": empty, "indexes": indexes or empty, "keys": keys or empty}


def test_a_unique_that_kept_its_name_and_changed_shape_is_dropped_before_it_is_added():
    """MySQL answers a second constraint of the same name with duplicate key name, and stops at that statement."""
    changed = {"missing": [("subscription_plan", "subscription_plan_uuid", 0, "uuid", "")], "extra": [("subscription_plan", "subscription_plan_uuid", 0, "code", "")]}

    lines = statements_for(shapes(indexes=changed), {})
    dropping = lines.index("DROP INDEX subscription_plan_uuid ON subscription_plan;")

    assert "subscription_plan_uuid" in lines[dropping + 1]


def test_a_key_whose_rule_changed_goes_by_the_name_the_database_gave_it_before_the_new_one_is_added():
    """Added alone, the new key sits beside the old one, and the old rule keeps being enforced."""
    changed = {"missing": [("commerce_product", "credits_currency_id", "currency", "id", "RESTRICT")], "extra": [("commerce_product", "credits_currency_id", "currency", "id", "CASCADE")]}

    lines = statements_for(shapes(keys=changed), {("commerce_product", "credits_currency_id"): "commerce_product_ibfk_2"})
    dropping = lines.index("ALTER TABLE commerce_product DROP FOREIGN KEY commerce_product_ibfk_2;")

    assert "FOREIGN KEY(credits_currency_id)" in lines[dropping + 1]


def test_a_key_that_is_only_missing_is_added_and_nothing_is_dropped():
    added = {"missing": [("commerce_product", "credits_currency_id", "currency", "id", "RESTRICT")], "extra": []}

    lines = statements_for(shapes(keys=added), {})

    assert not any("DROP" in line for line in lines)
    assert any("FOREIGN KEY(credits_currency_id)" in line for line in lines)
