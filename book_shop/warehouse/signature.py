import hashlib
import hmac
import time


class InvalidSignature(Exception):
    pass


def verify(secret: str, timestamp: str, signature: str, body: bytes, tolerance: int):
    """Check ``HMAC-SHA256(secret, "<timestamp>.<body>")`` and timestamp freshness."""
    try:
        age = abs(time.time() - int(timestamp))
    except (TypeError, ValueError) as exc:
        raise InvalidSignature("bad timestamp") from exc
    if age > tolerance:
        raise InvalidSignature("stale timestamp")  # replay protection
    expected = (
        "sha256="
        + hmac.new(
            secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
    )
    if not hmac.compare_digest(expected, signature or ""):
        raise InvalidSignature("signature mismatch")
