import hashlib


def generate_fingerprint(error_type: str, stacktrace: str) -> str:
    """Generate a fingerprint from error_type and first 3 stack frames."""
    lines = [l.strip() for l in stacktrace.strip().splitlines() if l.strip()]
    frames = lines[:3]
    raw = f"{error_type}|{'|'.join(frames)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
