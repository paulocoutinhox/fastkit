"""A postal code is a whole address in the countries that have somebody to ask, and nothing at all in the rest."""

import httpx2
import pytest

import helpers.postal_code_lookup as helpers_postal_code_lookup_module
import helpers.via_cep as helpers_via_cep_module
from enums.postal_code_provider import PostalCodeProvider
from helpers import postal_code

FOUND = {"cep": "01310-100", "logradouro": "Avenida Paulista", "complemento": "de 612 a 1510", "bairro": "Bela Vista", "localidade": "São Paulo", "uf": "SP"}


def answering(monkeypatch, status: int, body: dict):
    async def responder(self, request):
        return httpx2.Response(status, json=body)

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", responder)


async def test_a_code_the_service_knows_answers_the_address_it_stands_for(monkeypatch):
    answering(monkeypatch, 200, FOUND)

    place = await postal_code.find(PostalCodeProvider.VIACEP, "01310-100")

    assert place.line1 == "Avenida Paulista"
    assert place.district == "Bela Vista"
    assert place.city == "São Paulo"
    assert place.state == "SP"


@pytest.mark.parametrize("code", ["1234567", "123456789", "0131010a", ""])
async def test_a_code_of_any_other_shape_is_refused_here_instead_of_asked_about(monkeypatch, code):
    """The service answers 400 to anything but eight digits, so the length is what decides whether it is worth asking."""

    async def never(self, request):
        raise AssertionError("the service was asked about a code it would have refused")

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", never)

    assert await postal_code.find(PostalCodeProvider.VIACEP, code) is None


async def test_a_code_nobody_knows_is_not_an_address(monkeypatch):
    """A code that does not exist is answered with a status of 200 and `erro` in the body, so the body is what says so."""
    answering(monkeypatch, 200, {"erro": "true"})

    assert await postal_code.find(PostalCodeProvider.VIACEP, "00000000") is None


async def test_a_service_that_did_not_answer_is_not_an_address_either(monkeypatch):
    answering(monkeypatch, 500, {})

    assert await postal_code.find(PostalCodeProvider.VIACEP, "01310100") is None


async def test_a_body_missing_the_fields_answers_what_it_has(monkeypatch):
    """A code of a place with no street name answers the city and the state, and an empty line where the street would be."""
    answering(monkeypatch, 200, {"localidade": "Brasília", "uf": "DF"})

    place = await postal_code.find(PostalCodeProvider.VIACEP, "70000000")

    assert (place.line1, place.district, place.city) == ("", "", "Brasília")


def test_a_provider_that_answers_nothing_is_refused_where_it_is_built():
    """Building one happens on import, so a provider missing half its contract stops the process instead of a request."""
    with pytest.raises(TypeError):
        type("Empty", (helpers_postal_code_lookup_module.PostalCodeLookup,), {})()


async def test_a_code_answered_with_no_place_found_nothing(monkeypatch):
    """A body that carries neither a city nor a state names no place, and an empty address drawn into a form reads as a lookup that worked."""

    async def answer(self, *args, **kwargs):
        return httpx2.Response(200, json={"logradouro": "", "bairro": "", "localidade": "", "uf": ""})

    monkeypatch.setattr(httpx2.AsyncClient, "get", answer)

    assert await helpers_via_cep_module.ViaCep().find("01001000") is None
