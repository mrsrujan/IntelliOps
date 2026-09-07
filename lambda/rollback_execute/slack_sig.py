"""
Slack request signature verification.

Slack signs every interactive payload with HMAC-SHA256 of the body against
the app's signing secret. Verifying it is the only defence against someone
forging a rollback callback to our public API Gateway.
"""

import hashlib
import hmac
import time


def verify(body: str, timestamp: str, signature: str, signing_secret: str) -> bool:
    """Return True iff the signature matches and the request is fresh (<5 min)."""
    if not signature or not timestamp:
        return False

    try:
        ts = int(timestamp)
    except ValueError:
        return False

    # Reject stale requests to prevent replay attacks
    if abs(time.time() - ts) > 300:
        return False

    basestring = f"v0:{timestamp}:{body}".encode()
    expected = "v0=" + hmac.new(
        signing_secret.encode(), basestring, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
