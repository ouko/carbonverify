"""Client IP extraction with trusted-proxy awareness."""

from fastapi import Request


def get_client_ip(request: Request, trusted_proxies: set[str] | None = None) -> str:
    """Return the most trustworthy client IP for the request.

    If the immediate peer is in the trusted-proxies set, look at
    X-Forwarded-For / X-Real-IP. Otherwise return the direct peer IP.
    """
    if trusted_proxies is None:
        trusted_proxies = set()

    peer_host = request.client.host if request.client else None
    if peer_host and peer_host not in trusted_proxies:
        return peer_host or "unknown"

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For is client, proxy1, proxy2, ...
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    return peer_host or "unknown"
