import jwt
import pytest

from helpers.security import create_token, decode_token, decrypt, encrypt, generate_token, hash_password, verify_password


async def test_password_round_trip():
    encoded = await hash_password("s3cret-password")

    assert encoded != "s3cret-password"
    assert await verify_password("s3cret-password", encoded) is True
    assert await verify_password("another-password", encoded) is False


async def test_verify_password_refuses_a_broken_hash():
    assert await verify_password("s3cret-password", "not-a-hash") is False


def test_token_carries_the_subject_and_never_expires():
    token = create_token("9f2c-um-token", "administrator", 0)
    claims = decode_token(token)

    assert claims["sub"] == "9f2c-um-token"
    assert claims["role"] == "administrator"
    assert "exp" not in claims


def test_token_signed_with_another_key_is_refused():
    token = jwt.encode({"sub": "1"}, "another-key-nobody-here-ever-signed-with", algorithm="HS256")

    with pytest.raises(jwt.PyJWTError):
        decode_token(token)


def test_generate_token_is_unique():
    assert generate_token() != generate_token()


def test_encryption_round_trip():
    encrypted = encrypt("provider-secret")

    assert encrypted != "provider-secret"
    assert decrypt(encrypted) == "provider-secret"


@pytest.mark.parametrize("value", [None, ""])
def test_encrypt_keeps_an_empty_value_out_of_storage(value):
    assert encrypt(value) is None
    assert decrypt(value) is None


def test_decrypt_of_a_tampered_value_answers_nothing():
    assert decrypt("not-a-token") is None
