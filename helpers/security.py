"""What a password, a token and a stored secret are worth, and nothing else touches any of them."""

import asyncio
import base64
import hashlib
import logging
import secrets

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from helpers.dates import now
from helpers.settings import settings

logger = logging.getLogger(__name__)

password_hasher = PasswordHasher(memory_cost=settings.security.password_memory_cost, time_cost=settings.security.password_time_cost, parallelism=settings.security.password_parallelism)

# A login nobody has is verified against this, because skipping the hash makes the answer time alone say which accounts are here.
no_such_account = password_hasher.hash(secrets.token_urlsafe(32))


def key_from(passphrase: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest()))


# The first key writes and every one of them reads, so a key is replaced by putting the new one in front and rewriting what is stored.
fernet = MultiFernet([key_from(passphrase) for passphrase in settings.security.encryption_keys])


def settled(raw_password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, raw_password)
    except (Argon2Error, InvalidHashError):
        return False


# Argon2 is meant to cost tens of milliseconds of cpu, and spending them on the loop freezes every other request this worker is answering.
async def hash_password(raw_password: str) -> str:
    return await asyncio.to_thread(password_hasher.hash, raw_password)


async def verify_password(raw_password: str, password_hash: str) -> bool:
    return await asyncio.to_thread(settled, raw_password, password_hash)


def create_token(user_token: str, role: str, session_epoch: int) -> str:
    """The token carries no expiration on purpose, so a session ends when the account changes and not when a clock runs out."""
    claims = {"sub": user_token, "role": role, "epoch": session_epoch, "iat": int(now().timestamp())}

    return jwt.encode(claims, settings.security.secret_key, algorithm=settings.security.algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.security.secret_key, algorithms=[settings.security.algorithm])


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def encrypt(raw_value: str | None) -> str | None:
    if raw_value is None or raw_value == "":
        return None

    return fernet.encrypt(raw_value.encode()).decode()


def decrypt(encrypted_value: str | None) -> str | None:
    if not encrypted_value:
        return None

    try:
        return fernet.decrypt(encrypted_value.encode()).decode()
    except InvalidToken:
        # A stored secret this key cannot open reads exactly like one that was never set, and saying so is what tells the two apart.
        logger.error("[security] a stored secret could not be decrypted with the configured key")

        return None
