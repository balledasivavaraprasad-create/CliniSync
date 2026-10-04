import hashlib

def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def compute_fingerprint(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
