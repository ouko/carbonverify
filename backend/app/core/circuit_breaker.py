"""Circuit breaker pattern for external API calls."""

import asyncio
import time
from enum import Enum
from functools import wraps
from typing import Callable, Optional, TypeVar
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Args:
        name: Identifier for logging
        failure_threshold: Number of consecutive failures before opening
        recovery_timeout: Seconds to wait before trying half-open
        expected_exception: Exception types that count as failures
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: tuple = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("circuit_breaker_half_open", name=self.name)
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_failure_time = None
                logger.info("circuit_breaker_closed", name=self.name)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    reason="half_open_failure",
                    failure_count=self.failure_count,
                )
            elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_opened",
                    name=self.name,
                    reason="threshold_exceeded",
                    failure_count=self.failure_count,
                )

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Global circuit breakers for external services
CIRCUIT_BREAKERS = {
    "kimi_api": CircuitBreaker("kimi_api", failure_threshold=3, recovery_timeout=30.0),
    "radix_gateway": CircuitBreaker("radix_gateway", failure_threshold=5, recovery_timeout=60.0),
    "whatsapp_meta": CircuitBreaker("whatsapp_meta", failure_threshold=3, recovery_timeout=30.0),
    "verra_registry": CircuitBreaker("verra_registry", failure_threshold=5, recovery_timeout=120.0),
    "gold_standard_registry": CircuitBreaker("gold_standard_registry", failure_threshold=5, recovery_timeout=120.0),
}


def with_circuit_breaker(service_name: str):
    """Decorator to wrap a function with circuit breaker protection."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cb = CIRCUIT_BREAKERS.get(service_name)
            if not cb:
                return await func(*args, **kwargs)
            return await cb.call(func, *args, **kwargs)
        return wrapper
    return decorator
