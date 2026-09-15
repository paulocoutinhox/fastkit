"""Every contract a provider implements is written one way, so a mistake in a new one fails where the others fail."""

import enum
import importlib
import inspect
import pathlib
import re

from services.gateway import PaymentProvider

DECLARING = ["helpers", "services"]


def contracts() -> list[tuple[str, dict, type]]:
    """Every map of providers, found in the source with the contract it answers and the enum it is keyed by."""
    found = []

    for path in sorted(entry for folder in DECLARING for entry in pathlib.Path(folder).rglob("*.py")):
        source = path.read_text()

        if not re.search(r"^PROVIDERS[:=]", source, re.M):
            continue

        module = importlib.import_module(str(path.with_suffix("")).replace("/", "."))
        table = module.PROVIDERS
        keys = {type(key) for key in table}
        answers = {type(value) if not inspect.isclass(value) else value for value in table.values()}

        assert len(keys) == 1, f"{path}: a map keyed by more than one kind of thing"

        base = next(iter({parent for answer in answers for parent in answer.__mro__ if parent.__name__ not in ("object", "ABC") and parent not in answers}), None)
        found.append((str(path), table, keys.pop(), base))

    return found


def test_every_provider_is_indexed_by_an_enum_it_answers_for_whole():
    """A value nobody implemented is a five hundred wherever it is read, and a map reached by a fall-through hides it."""
    read = contracts()

    assert len(read) >= 5, f"the scan found only {len(read)} of them, so it is proving nothing"

    for where, table, keyed_by, _ in read:
        assert issubclass(keyed_by, enum.Enum), f"{where} is keyed by {keyed_by.__name__} and not by an enum"
        assert set(table) == set(keyed_by), f"{where} has nothing for {sorted(str(value) for value in set(keyed_by) - set(table))}"


def test_every_contract_refuses_a_provider_that_implements_nothing():
    """A base that only raises inside its methods lets an incomplete provider through, and it breaks in a request instead."""
    for where, _, _, base in contracts():
        assert base is not None, f"{where} answers with something that implements no contract"

        # The gateway refuses at the definition, and the others at the construction that happens on this very import.
        if base is PaymentProvider:
            continue

        empty = type("Empty", (base,), {})

        try:
            empty()
        except TypeError:
            continue

        raise AssertionError(f"{where}: {base.__name__} builds a provider that implements nothing, so it breaks in a request instead of here")


def test_the_gateway_refuses_a_provider_missing_either_half_of_its_contract():
    """Authenticating and reading are both named mandatory, and forgetting the first is forgetting what proves the caller."""
    from services.gateway import Credential

    for missing in ("authenticate", "read"):
        body = {"event_stated": True, "credentials": (Credential(field="stripe_webhook_secret", label="Signing secret", hint="wherever"),)}
        body |= {name: (lambda self, *args, **kwargs: None) for name in ("authenticate", "read") if name != missing}

        try:
            type("Careless", (PaymentProvider,), body)
        except TypeError as error:
            assert missing in str(error)
            continue

        raise AssertionError(f"a gateway with no {missing} was accepted")


def test_every_provider_of_a_contract_answers_each_method_the_same_way():
    """One provider waiting where another does not is the difference between a value and an object nobody reads, and the gateway is where that costs the most: an `authenticate` written as a coroutine is never waited for, so it never runs and leaves the webhook open to whoever finds the key."""
    compared = 0

    for where, table, _, base in contracts():
        providers = [value if inspect.isclass(value) else type(value) for value in table.values()]
        named = {name for provider in providers for name in vars(provider) if callable(vars(provider)[name]) and hasattr(base, name)}

        for name in sorted(named):
            shapes = {(inspect.iscoroutinefunction(getattr(provider, name)), inspect.isasyncgenfunction(getattr(provider, name))) for provider in providers if name in vars(provider)}

            if len(providers) < 2:
                continue

            compared += 1

            assert len(shapes) == 1, f"{where}: the providers write {name} in {len(shapes)} different shapes, and the caller reads one of them"

    assert compared >= 8, f"the scan compared only {compared} methods, so it is proving nothing"


def test_the_documented_number_of_contracts_is_the_number_the_scan_finds():
    """A count written in prose is the one thing a scan that finds its own subjects cannot keep honest by itself."""
    written = pathlib.Path("CLAUDE.md").read_text().replace("**", "")
    stated = {int(number) for number in re.findall(r"(\d+) coisas neste projeto são um contrato", written)}

    assert stated == {len(contracts())}, f"the documentation counts {stated} contracts and the scan finds {len(contracts())}"
