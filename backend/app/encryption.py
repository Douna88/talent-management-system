"""Field-level encryption (Fernet) for sensitive account fields."""
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import ENCRYPTION_KEY


def _get_fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(ENCRYPTION_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_text(plain: str) -> str:
    """Encrypt a plaintext string. Returns empty string for empty input."""
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher: str) -> str:
    """Decrypt an encrypted string."""
    if not cipher:
        return ""
    try:
        return _get_fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def mask_account(account: str) -> str:
    """Mask an account number keeping first 4 and last 4 digits."""
    if not account:
        return ""
    if len(account) <= 8:
        return account
    return account[:4] + "*" * (len(account) - 8) + account[-4:]
