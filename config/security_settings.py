from pydantic import BaseModel


class SecuritySettings(BaseModel):
    secret_key: str
    algorithm: str = "HS256"

    # The first key is what a secret is written with and every one of them opens what is stored, which is what makes a key able to be replaced.
    encryption_keys: list[str]

    # How many wrong passwords an account answers before it stops answering, and for how long it then stops.
    sign_in_attempts: int = 5
    sign_in_cooldown: int = 60
    sign_in_cooldown_max: int = 900

    # The cost of a hash is what protects a stolen table, and the defaults are what argon2 recommends for a server.
    password_memory_cost: int = 65_536
    password_time_cost: int = 3
    password_parallelism: int = 4
