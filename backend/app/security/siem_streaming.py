"""SIEM streaming for audit logs — Splunk HEC and generic HTTP endpoints."""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_MAX_BATCH_SIZE = 100
_BATCH_FLUSH_INTERVAL_SECONDS = 10


class SIEMStreamer:
    """Stream audit log entries to external SIEM systems."""

    def __init__(self):
        self._enabled = bool(settings.SIEM_ENDPOINT)
        self._endpoint = settings.SIEM_ENDPOINT
        self._token = settings.SIEM_TOKEN
        self._source = settings.SIEM_SOURCE or "carbonverify"
        self._index = settings.SIEM_INDEX or "main"
        self._batch: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    async def start(self):
        if self._enabled and self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self._flush_batch()

    async def send(self, entry: Dict[str, Any]):
        if not self._enabled:
            return
        async with self._lock:
            self._batch.append(entry)
            if len(self._batch) >= _MAX_BATCH_SIZE:
                await self._flush_batch_unlocked()

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(_BATCH_FLUSH_INTERVAL_SECONDS)
            await self._flush_batch()

    async def _flush_batch(self):
        async with self._lock:
            await self._flush_batch_unlocked()

    async def _flush_batch_unlocked(self):
        if not self._batch:
            return
        batch = self._batch[:]
        self._batch.clear()
        try:
            await self._send_batch(batch)
        except Exception as exc:
            logger.error("siem_batch_send_failed", count=len(batch), error=str(exc))

    async def _send_batch(self, entries: List[Dict[str, Any]]):
        if not entries:
            return

        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Splunk {self._token}"

        payload = self._build_payload(entries)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self._endpoint, headers=headers, content=payload)
            response.raise_for_status()

        logger.info("siem_batch_sent", count=len(entries), endpoint=self._endpoint)

    def _build_payload(self, entries: List[Dict[str, Any]]) -> str:
        # Default format: Splunk HEC event format (one JSON object per line)
        lines = []
        for entry in entries:
            event = {
                "time": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "source": self._source,
                "sourcetype": "_json",
                "index": self._index,
                "event": entry,
            }
            lines.append(json.dumps(event, default=str))
        return "\n".join(lines)


# Singleton instance
_streamer: Optional[SIEMStreamer] = None


def get_siem_streamer() -> SIEMStreamer:
    global _streamer
    if _streamer is None:
        _streamer = SIEMStreamer()
    return _streamer
