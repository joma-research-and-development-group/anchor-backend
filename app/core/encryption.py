import json

from cryptography.fernet import Fernet

from app.core.config import settings

_KEY: bytes | None = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        secret = settings.JWT_SECRET.encode()
        import base64
        import hashlib
        _KEY = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return _KEY


def encrypt_credentials(data: dict) -> bytes:
    f = Fernet(_get_key())
    return f.encrypt(json.dumps(data).encode())


def decrypt_credentials(data: bytes) -> dict:
    f = Fernet(_get_key())
    return json.loads(f.decrypt(data).decode())
