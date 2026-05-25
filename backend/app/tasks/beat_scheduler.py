"""Celery Beat scheduler with Redis-based leader election.

Prevents multiple Celery Beat pods from running duplicate scheduled tasks
in a Kubernetes environment.
"""

import time
import redis
from celery.beat import Scheduler
from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

BEAT_LOCK_KEY = "celery_beat:leader_lock"
BEAT_LOCK_TTL = 60  # seconds


class LeaderElectionScheduler(Scheduler):
    """Celery Beat scheduler that only runs on the leader node."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
        )
        self._lock_identifier = f"{self.app.main_name}:{time.time()}"
        self._is_leader = False

    def tick(self, *args, **kwargs):
        if not self._acquire_or_refresh_lock():
            if self._is_leader:
                logger.info("celery_beat_lost_leadership", lock_id=self._lock_identifier)
                self._is_leader = False
            # Sleep briefly to avoid tight spinning when not leader
            time.sleep(5)
            return

        if not self._is_leader:
            logger.info("celery_beat_acquired_leadership", lock_id=self._lock_identifier)
            self._is_leader = True

        return super().tick(*args, **kwargs)

    def _acquire_or_refresh_lock(self) -> bool:
        """Try to acquire or extend the leader lock."""
        try:
            # Use Redis SET NX EX for atomic lock acquisition
            acquired = self._redis.set(
                BEAT_LOCK_KEY,
                self._lock_identifier,
                nx=True,
                ex=BEAT_LOCK_TTL,
            )
            if acquired:
                return True

            # Lock exists — check if we own it
            current_owner = self._redis.get(BEAT_LOCK_KEY)
            if current_owner and current_owner.decode("utf-8") == self._lock_identifier:
                # Extend our lock
                self._redis.expire(BEAT_LOCK_KEY, BEAT_LOCK_TTL)
                return True

            return False
        except redis.RedisError as exc:
            logger.error("celery_beat_lock_error", error=str(exc))
            # If Redis is down, assume leadership to avoid total scheduling loss
            return True

    def close(self):
        try:
            if self._is_leader:
                current_owner = self._redis.get(BEAT_LOCK_KEY)
                if current_owner and current_owner.decode("utf-8") == self._lock_identifier:
                    self._redis.delete(BEAT_LOCK_KEY)
                    logger.info("celery_beat_released_leadership", lock_id=self._lock_identifier)
        except redis.RedisError as exc:
            logger.error("celery_beat_release_error", error=str(exc))
        finally:
            super().close()
