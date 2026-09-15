from __future__ import annotations
import hashlib
import bcrypt
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
def is_bcrypt_hash(value: str | None) -> bool:
    return bool(value) and value.startswith(("$2a$", "$2b$", "$2y$"))
def verify_password(password: str, stored_hash: str | None) -> tuple[bool, bool]:
    if not stored_hash: return False, False
    if is_bcrypt_hash(stored_hash):
        try: return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")), False
        except ValueError: return False, False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return legacy == stored_hash, legacy == stored_hash
