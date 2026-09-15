"""The name an account is called by is read by whoever is looking at the screen, so it falls through what is safe to show and never through what identifies the person."""

import pytest

from helpers.text import display_name


class Account:
    def __init__(self, **fields):
        self.id = fields.pop("id", 36)

        for name in ("nickname", "first_name", "last_name", "email", "username", "mobile_phone", "document"):
            setattr(self, name, fields.pop(name, None))

        assert not fields, fields


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({"nickname": "Paulinho"}, "Paulinho"),
        ({"nickname": "Paulinho", "first_name": "Paulo", "email": "a@acme.com"}, "Paulinho"),
        ({"first_name": "Paulo", "last_name": "Coutinho"}, "Paulo Coutinho"),
        ({"first_name": "Paulo"}, "Paulo"),
        ({"last_name": "Coutinho"}, "Coutinho"),
        ({"username": "paulo", "email": "ada@acme.com"}, "paulo"),
        ({"email": "ada.lovelace@acme.com"}, "ada.lovelace"),
        ({}, "#36"),
    ],
)
def test_the_name_falls_through_what_the_account_actually_has(fields, expected):
    assert display_name(Account(**fields)) == expected


@pytest.mark.parametrize("fields", [{"mobile_phone": "11999999999"}, {"document": "12345678901"}])
def test_what_identifies_the_person_is_never_the_name_they_are_called_by(fields):
    assert display_name(Account(**fields)) == "#36"


@pytest.mark.parametrize("fields", [{"nickname": "   "}, {"first_name": "  ", "last_name": "  "}])
def test_whitespace_is_not_a_name(fields):
    assert display_name(Account(email="ada@acme.com", **fields)) == "ada"


def test_the_parts_of_a_name_are_trimmed_and_joined_by_one_space():
    assert display_name(Account(first_name="  Paulo ", last_name=" Coutinho  ")) == "Paulo Coutinho"


async def test_the_api_answers_the_same_name_the_lookup_does(client, admin_headers, administrator):
    listed = (await client.get("/api/users?limit=1", headers=admin_headers)).json()["items"][0]
    lookup = (await client.get("/api/users/lookup", headers=admin_headers)).json()["items"]

    assert listed["displayName"]
    assert {row["label"] for row in lookup} == {listed["displayName"]}
