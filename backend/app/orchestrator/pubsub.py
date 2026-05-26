"""Redis pub/sub layer for inter-agent communication."""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

import redis.asyncio as redis

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AgentPubSub:
    """Redis pub/sub for agent communication and WebSocket bridging."""

    _instance: Optional["AgentPubSub"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._listeners: list = []
        self._initialized = True

    async def connect(self):
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30,
                    retry_on_timeout=True,
                )
                self._pubsub = self._redis.pubsub()
                await self._pubsub.subscribe("orchestrator:events", "agent:results")
                logger.info("redis_pubsub_connected")
                task = asyncio.create_task(self._listen_loop())
                task.add_done_callback(self._on_listen_done)
            except Exception as exc:
                logger.error("redis_pubsub_connect_failed", error=str(exc))
                self._redis = None
                self._pubsub = None
                raise

    def _on_listen_done(self, task: asyncio.Task):
        """Log unhandled exceptions from the listen loop."""
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("redis_pubsub_listen_error", error=str(exc))

    async def disconnect(self):
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("redis_pubsub_disconnected")

    async def _listen_loop(self):
        """Background task that listens to Redis channels and forwards to local listeners."""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        channel = message["channel"]
                        for listener in self._listeners:
                            try:
                                await listener(channel, payload)
                            except Exception as exc:
                                logger.error("pubsub_listener_error", error=str(exc))
                    except json.JSONDecodeError:
                        logger.warning("pubsub_invalid_json", data=message["data"][:200])
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("pubsub_listen_loop_error", error=str(exc))

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Dict[str, Any]], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def publish_event(self, event_type: str, payload: Dict[str, Any]):
        """Publish an orchestrator event to all subscribers."""
        if self._redis is None:
            await self.connect()
        message = json.dumps({"type": event_type, **payload})
        await self._redis.publish("orchestrator:events", message)
        logger.debug("pubsub_event_published", event_type=event_type)

    async def publish_agent_result(self, agent_type: str, project_id: str, result: Dict[str, Any]):
        """Publish an agent execution result."""
        if self._redis is None:
            await self.connect()
        message = json.dumps(
            {
                "agent_type": agent_type,
                "project_id": project_id,
                "result": result,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )
        await self._redis.publish("agent:results", message)
        logger.debug("pubsub_agent_result_published", agent_type=agent_type, project_id=project_id)

    async def publish_project_update(self, project_id: str, update: Dict[str, Any]):
        """Publish a project-specific update for WebSocket clients."""
        if self._redis is None:
            await self.connect()
        channel = f"project:{project_id}"
        message = json.dumps({"project_id": project_id, **update})
        await self._redis.publish(channel, message)


# Global singleton
agent_pubsub = AgentPubSub()
