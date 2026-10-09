import hashlib
import os

def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def compute_fingerprint(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${hashed}"

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        salt, expected_hash = hashed_password.split("$")
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return computed == expected_hash
    except Exception:
        return False
