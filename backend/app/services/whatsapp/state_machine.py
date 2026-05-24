"""Redis-based conversation state machine for WhatsApp bot."""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import redis

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Redis key prefixes
CONVERSATION_PREFIX = "cv:whatsapp:conv"
SESSION_PREFIX = "cv:whatsapp:session"
RATE_LIMIT_PREFIX = "cv:whatsapp:ratelimit"


class ConversationStateManager:
    """Manages WhatsApp conversation state in Redis with PostgreSQL fallback."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    def get_conversation_key(self, phone_number: str) -> str:
        return f"{CONVERSATION_PREFIX}:{phone_number}"

    def get_session_key(self, phone_number: str) -> str:
        return f"{SESSION_PREFIX}:{phone_number}"

    def get_state(self, phone_number: str) -> Dict[str, Any]:
        """Get current conversation state for a phone number."""
        try:
            r = self._get_redis()
            key = self.get_conversation_key(phone_number)
            data = r.get(key)
            if data:
                return json.loads(data)
        except Exception as exc:
            logger.error("redis_get_state_error", error=str(exc), phone=phone_number)
        return self._default_state()

    def set_state(self, phone_number: str, state: Dict[str, Any], ttl: int = 86400):
        """Set conversation state with TTL (default 24 hours)."""
        try:
            r = self._get_redis()
            key = self.get_conversation_key(phone_number)
            state["updated_at"] = datetime.utcnow().isoformat()
            r.setex(key, ttl, json.dumps(state))
        except Exception as exc:
            logger.error("redis_set_state_error", error=str(exc), phone=phone_number)

    def delete_state(self, phone_number: str):
        """Delete conversation state."""
        try:
            r = self._get_redis()
            r.delete(self.get_conversation_key(phone_number))
            r.delete(self.get_session_key(phone_number))
        except Exception as exc:
            logger.error("redis_delete_state_error", error=str(exc), phone=phone_number)

    def _default_state(self) -> Dict[str, Any]:
        return {
            "flow": "idle",
            "step": 0,
            "language": "en",
            "project_id": None,
            "enumerator_id": None,
            "responses": {},
            "photos": [],
            "message_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    def start_flow(self, phone_number: str, flow: str, project_id: Optional[str] = None,
                   enumerator_id: Optional[str] = None, language: str = "en"):
        """Start a new conversation flow."""
        state = self._default_state()
        state["flow"] = flow
        state["step"] = 0
        state["language"] = language
        state["project_id"] = project_id
        state["enumerator_id"] = enumerator_id
        self.set_state(phone_number, state)
        logger.info("flow_started", phone=phone_number, flow=flow, project_id=project_id)

    def advance_step(self, phone_number: str, response_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Advance to the next step and optionally store response."""
        state = self.get_state(phone_number)
        if response_data:
            step_key = f"step_{state['step']}"
            state["responses"][step_key] = response_data
        state["step"] += 1
        state["message_count"] += 1
        self.set_state(phone_number, state)
        return state

    def store_response(self, phone_number: str, question_id: str, value: Any, valid: bool = True,
                       errors: Optional[list] = None):
        """Store a survey response."""
        state = self.get_state(phone_number)
        state["responses"][question_id] = {
            "value": value,
            "valid": valid,
            "errors": errors or [],
            "timestamp": datetime.utcnow().isoformat(),
        }
        state["message_count"] += 1
        self.set_state(phone_number, state)

    def store_photo(self, phone_number: str, photo_data: Dict[str, Any]):
        """Store photo metadata."""
        state = self.get_state(phone_number)
        state["photos"].append({
            **photo_data,
            "timestamp": datetime.utcnow().isoformat(),
        })
        state["message_count"] += 1
        self.set_state(phone_number, state)

    def get_responses(self, phone_number: str) -> Dict[str, Any]:
        """Get all stored responses."""
        state = self.get_state(phone_number)
        return state.get("responses", {})

    def is_rate_limited(self, phone_number: str, max_messages: int = 50, window_seconds: int = 3600) -> bool:
        """Check if phone number is rate limited."""
        try:
            r = self._get_redis()
            key = f"{RATE_LIMIT_PREFIX}:{phone_number}"
            current = r.incr(key)
            if current == 1:
                r.expire(key, window_seconds)
            return current > max_messages
        except Exception as exc:
            logger.error("rate_limit_check_error", error=str(exc), phone=phone_number)
            return False

    def get_active_conversations(self, pattern: str = "*") -> list:
        """Get list of active conversation keys."""
        try:
            r = self._get_redis()
            keys = r.keys(f"{CONVERSATION_PREFIX}:{pattern}")
            return [k.replace(f"{CONVERSATION_PREFIX}:", "") for k in keys]
        except Exception as exc:
            logger.error("redis_scan_error", error=str(exc))
            return []


# Global singleton
conversation_state = ConversationStateManager()
