"""Synthetic Actor Factory — generates identifiable test personas."""

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.validation_engine.models import SyntheticActor, SyntheticActorType


# ─── Behavioral Profiles ──────────────────────────────────────────────────────

BEHAVIOR_PROFILES: Dict[str, Dict[str, Any]] = {
    "impatient_mobile_user": {
        "typing_delay_ms": {"min": 50, "max": 150},
        "page_load_timeout_ms": 3000,
        "retry_on_error": True,
        "max_retries": 2,
        "navigation_pattern": "rapid_tap",
        "device": "mobile",
    },
    "careful_desktop_admin": {
        "typing_delay_ms": {"min": 200, "max": 400},
        "page_load_timeout_ms": 10000,
        "retry_on_error": False,
        "max_retries": 0,
        "navigation_pattern": "methodical_click",
        "device": "desktop",
    },
    "api_integration_service": {
        "request_timeout_ms": 5000,
        "retry_on_error": True,
        "max_retries": 5,
        "backoff_strategy": "exponential",
        "rate_limit_rps": 10,
    },
    "slow_rural_connection": {
        "typing_delay_ms": {"min": 300, "max": 800},
        "page_load_timeout_ms": 20000,
        "retry_on_error": True,
        "max_retries": 3,
        "navigation_pattern": "slow_deliberate",
        "device": "mobile",
        "connection_quality": "2g",
    },
    "automated_test_bot": {
        "typing_delay_ms": {"min": 0, "max": 10},
        "page_load_timeout_ms": 5000,
        "retry_on_error": True,
        "max_retries": 1,
        "navigation_pattern": "instant",
        "device": "headless",
    },
}

# ─── Context Templates ────────────────────────────────────────────────────────

CONTEXT_TEMPLATES: Dict[SyntheticActorType, List[Dict[str, Any]]] = {
    SyntheticActorType.user: [
        {
            "locale": "en-KE",
            "timezone": "Africa/Nairobi",
            "language_preference": "sw",
            "onboarding_complete": True,
            "project_access": ["demo_project_1"],
        },
        {
            "locale": "en-US",
            "timezone": "America/New_York",
            "language_preference": "en",
            "onboarding_complete": False,
            "project_access": [],
        },
    ],
    SyntheticActorType.admin: [
        {
            "locale": "en-GB",
            "timezone": "Europe/London",
            "permissions": ["all"],
            "mfa_enabled": True,
        },
    ],
    SyntheticActorType.service: [
        {
            "service_name": "carbon-calculation-worker",
            "version": "2.1.0",
            "endpoint": "http://worker.internal:8080",
        },
        {
            "service_name": "report-generator",
            "version": "1.5.2",
            "endpoint": "http://reports.internal:8080",
        },
    ],
    SyntheticActorType.external_system: [
        {
            "system_name": "verra_registry",
            "api_version": "v3",
            "auth_method": "oauth2",
        },
        {
            "system_name": "gold_standard_registry",
            "api_version": "v2",
            "auth_method": "api_key",
        },
    ],
    SyntheticActorType.browser: [
        {
            "browser": "chromium",
            "headless": True,
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.0",
        },
    ],
}

# ─── Identifiable Markers ─────────────────────────────────────────────────────

MARKER_TEMPLATES = {
    SyntheticActorType.user: {
        "email_suffix": "@synth.carbonverify.test",
        "phone_prefix": "+254700",
        "id_prefix": "SYNTH-U-",
    },
    SyntheticActorType.admin: {
        "email_suffix": "@synth-admin.carbonverify.test",
        "phone_prefix": "+254701",
        "id_prefix": "SYNTH-A-",
    },
    SyntheticActorType.service: {
        "id_prefix": "SYNTH-SVC-",
        "trace_header": "X-Synthetic-Actor",
    },
    SyntheticActorType.external_system: {
        "id_prefix": "SYNTH-EXT-",
        "trace_header": "X-Synthetic-External",
    },
    SyntheticActorType.browser: {
        "id_prefix": "SYNTH-BRW-",
        "dom_marker": "data-synthetic-actor-id",
    },
}


class SyntheticActorFactory:
    """Factory for creating and managing synthetic test actors."""

    def __init__(self):
        self._actor_cache: Dict[str, SyntheticActor] = {}

    async def create_actor(
        self,
        db: AsyncSession,
        name: str,
        actor_type: SyntheticActorType,
        profile_key: str = "impatient_mobile_user",
        custom_markers: Optional[Dict[str, Any]] = None,
        custom_behavior: Optional[Dict[str, Any]] = None,
        custom_context: Optional[Dict[str, Any]] = None,
    ) -> SyntheticActor:
        """Create a new synthetic actor and persist it."""
        profile = BEHAVIOR_PROFILES.get(profile_key, BEHAVIOR_PROFILES["impatient_mobile_user"])
        behavior = {**profile, **(custom_behavior or {})}

        markers = self._generate_markers(actor_type, name)
        if custom_markers:
            markers.update(custom_markers)

        context = self._generate_context(actor_type)
        if custom_context:
            context.update(custom_context)

        actor = SyntheticActor(
            name=name,
            actor_type=actor_type,
            profile_key=profile_key,
            markers=markers,
            behavior_config=behavior,
            context_data=context,
            active=True,
            usage_count=0,
        )
        db.add(actor)
        await db.commit()
        await db.refresh(actor)
        self._actor_cache[str(actor.id)] = actor
        return actor

    async def get_actor(self, db: AsyncSession, actor_id: str) -> Optional[SyntheticActor]:
        """Get an actor by ID, using cache if available."""
        if actor_id in self._actor_cache:
            return self._actor_cache[actor_id]

        result = await db.execute(
            select(SyntheticActor).where(SyntheticActor.id == uuid.UUID(actor_id))
        )
        actor = result.scalar_one_or_none()
        if actor:
            self._actor_cache[actor_id] = actor
        return actor

    async def get_or_create_default_actor(
        self,
        db: AsyncSession,
        actor_type: SyntheticActorType = SyntheticActorType.user,
    ) -> SyntheticActor:
        """Get or create a default synthetic actor of the given type."""
        result = await db.execute(
            select(SyntheticActor)
            .where(
                SyntheticActor.actor_type == actor_type,
                SyntheticActor.active == True,
            )
            .order_by(SyntheticActor.usage_count.asc())
            .limit(1)
        )
        actor = result.scalar_one_or_none()
        if actor:
            return actor

        # Create default actor
        return await self.create_actor(
            db,
            name=f"default_{actor_type.value}_{uuid.uuid4().hex[:8]}",
            actor_type=actor_type,
        )

    async def mark_actor_used(self, db: AsyncSession, actor: SyntheticActor) -> None:
        """Increment usage counter and update last_used_at."""
        actor.usage_count += 1
        actor.last_used_at = datetime.now(timezone.utc)
        await db.commit()

    def _generate_markers(self, actor_type: SyntheticActorType, name: str) -> Dict[str, Any]:
        """Generate identifiable markers for an actor."""
        template = MARKER_TEMPLATES.get(actor_type, {})
        unique_id = f"{template.get('id_prefix', 'SYNTH-')}{uuid.uuid4().hex[:12].upper()}"

        markers = {
            "synthetic_actor_id": unique_id,
            "synthetic_actor_name": name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if "email_suffix" in template:
            markers["synthetic_email"] = f"{name.replace(' ', '_').lower()}{template['email_suffix']}"
        if "phone_prefix" in template:
            markers["synthetic_phone"] = f"{template['phone_prefix']}{random.randint(100000, 999999)}"
        if "trace_header" in template:
            markers["trace_header_name"] = template["trace_header"]
            markers["trace_header_value"] = unique_id
        if "dom_marker" in template:
            markers["dom_marker_name"] = template["dom_marker"]
            markers["dom_marker_value"] = unique_id

        return markers

    def _generate_context(self, actor_type: SyntheticActorType) -> Dict[str, Any]:
        """Generate default context data for an actor type."""
        templates = CONTEXT_TEMPLATES.get(actor_type, [])
        if templates:
            return random.choice(templates).copy()
        return {}

    async def list_available_actors(
        self,
        db: AsyncSession,
        actor_type: Optional[SyntheticActorType] = None,
    ) -> List[SyntheticActor]:
        """List available synthetic actors, optionally filtered by type."""
        query = select(SyntheticActor).where(SyntheticActor.active == True)
        if actor_type:
            query = query.where(SyntheticActor.actor_type == actor_type)
        result = await db.execute(query)
        return list(result.scalars().all())
