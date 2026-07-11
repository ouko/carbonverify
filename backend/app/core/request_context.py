"""Async-safe request context helpers."""

from contextvars import ContextVar
from typing import Optional

request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

trusted_proxies_ctx_var: ContextVar[set[str]] = ContextVar("trusted_proxies", default=set())


def set_request_id(request_id: str) -> None:
    request_id_ctx_var.set(request_id)


def get_request_id() -> Optional[str]:
    return request_id_ctx_var.get()


def set_trusted_proxies(proxies: set[str]) -> None:
    trusted_proxies_ctx_var.set(proxies)


def get_trusted_proxies() -> set[str]:
    return trusted_proxies_ctx_var.get()
