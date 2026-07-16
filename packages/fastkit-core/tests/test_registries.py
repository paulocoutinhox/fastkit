import pytest

from fastkit_core.registries.base import Registry, RegistryError


def test_register_and_get():
    registry = Registry[str]("things")
    registry.register("a", "alpha", source="pkg", priority=1)

    assert registry.get("a") == "alpha"
    assert registry.try_get("a") == "alpha"
    assert registry.try_get("missing") is None
    assert registry.contains("a")
    assert registry.keys() == ["a"]
    assert len(registry) == 1


def test_duplicate_key_raises():
    registry = Registry[str]("things")
    registry.register("a", "alpha", source="first")

    with pytest.raises(RegistryError, match="duplicate key 'a'"):
        registry.register("a", "beta", source="second")


def test_override_allowed_when_configured():
    registry = Registry[str]("things", allow_override=True)
    registry.register("a", "alpha")
    registry.register("a", "beta")

    assert registry.get("a") == "beta"


def test_get_missing_raises():
    registry = Registry[str]("things")

    with pytest.raises(RegistryError, match="not found"):
        registry.get("nope")


def test_priority_ordering_and_iteration():
    registry = Registry[str]("things")
    registry.register("low", "l", priority=1)
    registry.register("high", "h", priority=10)

    assert registry.values() == ["h", "l"]
    assert list(registry) == ["h", "l"]
    assert [entry.key for entry in registry.entries()] == ["high", "low"]


def test_freeze_blocks_registration():
    registry = Registry[str]("things")
    registry.freeze()

    assert registry.frozen

    with pytest.raises(RegistryError, match="frozen"):
        registry.register("a", "alpha")


def test_provider_registry_builds_and_extends():
    from fastkit_core.providers import ProviderRegistry

    providers = ProviderRegistry("cache")
    providers.register("memory", lambda settings: ("memory", settings))

    assert providers.build("memory", {"ttl": 5}) == ("memory", {"ttl": 5})

    providers.register("custom", lambda settings: "plugged")
    assert providers.build("custom", {}) == "plugged"

    with pytest.raises(ValueError, match="unknown cache provider 'ghost'"):
        providers.build("ghost", {})
