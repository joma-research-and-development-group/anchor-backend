import secrets

import bcrypt


def generate_api_key(mode_name: str) -> tuple[str, str, str]:
    """Generate an API key. Returns (raw_secret, prefix, bcrypt_hash)."""
    env = "live" if mode_name.lower() in ("live", "production", "prod") else "test"
    random_hex = secrets.token_hex(32)
    raw_secret = f"anchor_pk_{env}_{random_hex}"
    prefix = raw_secret[:20]
    key_hash = bcrypt.hashpw(raw_secret.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("utf-8")
    return raw_secret, prefix, key_hash


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify a raw API key against its stored hash."""
    return bcrypt.checkpw(raw_key.encode("utf-8")[:72], key_hash.encode("utf-8"))
