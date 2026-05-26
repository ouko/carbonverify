"""ClamAV virus scanning with graceful fallback.

Scans file buffers using a local clamd socket. If ClamAV is unreachable,
logs a warning and returns a safe fallback so uploads are not blocked.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import clamd

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScanStatus(str, Enum):
    clean = "clean"
    infected = "infected"
    error = "error"


@dataclass
class ScanResult:
    status: ScanStatus
    signature: Optional[str] = None
    message: Optional[str] = None


class ClamAVScanner:
    """Lightweight wrapper around clamd with connection health checks."""

    def __init__(self, socket_path: Optional[str] = None, host: Optional[str] = None, port: int = 3310):
        self._socket_path = socket_path
        self._host = host
        self._port = port
        self._client: Optional[clamd.ClamdUnixSocket] = None

    def _get_client(self) -> Optional[clamd.ClamdUnixSocket]:
        if self._client is not None:
            return self._client

        try:
            if self._socket_path:
                self._client = clamd.ClamdUnixSocket(path=self._socket_path)
            elif self._host:
                self._client = clamd.ClamdNetworkSocket(host=self._host, port=self._port)
            else:
                # Try default Unix socket first, then fallback to TCP
                try:
                    self._client = clamd.ClamdUnixSocket()
                except Exception:
                    self._client = clamd.ClamdNetworkSocket()
        except Exception as exc:
            logger.warning("clamav_client_init_failed", error=str(exc))
            return None

        return self._client

    def ping(self) -> bool:
        """Check if clamd is reachable."""
        client = self._get_client()
        if client is None:
            return False
        try:
            client.ping()
            return True
        except Exception:
            return False

    def _scan_sync(self, data: bytes) -> ScanResult:
        """Synchronous scan of a byte buffer."""
        client = self._get_client()
        if client is None:
            logger.warning("clamav_not_available", reason="Skipping virus scan — clamd unreachable")
            return ScanResult(status=ScanStatus.error, message="ClamAV not available")

        try:
            import io
            result = client.instream(io.BytesIO(data))
            # clamd returns {"stream": ("OK", None)} for clean files
            # or {"stream": ("FOUND", "Eicar-Test-Signature")} for infected
            if not result:
                return ScanResult(status=ScanStatus.clean)

            stream_result = result.get("stream")
            if stream_result is None:
                return ScanResult(status=ScanStatus.error, message="Unexpected clamd response format")

            status_str, signature = stream_result
            if status_str == "OK":
                return ScanResult(status=ScanStatus.clean)
            elif status_str == "FOUND":
                logger.warning("clamav_threat_detected", signature=signature, size=len(data))
                return ScanResult(status=ScanStatus.infected, signature=signature)
            else:
                return ScanResult(status=ScanStatus.error, message=f"Unknown clamd status: {status_str}")

        except clamd.BufferTooLongError:
            logger.warning("clamav_buffer_too_long", size=len(data))
            return ScanResult(status=ScanStatus.error, message="File too large for ClamAV stream scan")
        except Exception as exc:
            logger.error("clamav_scan_failed", error=str(exc), size=len(data))
            return ScanResult(status=ScanStatus.error, message=str(exc))

    async def scan_buffer(self, data: bytes) -> ScanResult:
        """Async scan of a byte buffer for malware.

        Offloads the synchronous clamd socket call to a thread pool.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scan_sync, data)


# Global singleton
_scanner: Optional[ClamAVScanner] = None


def get_scanner() -> ClamAVScanner:
    global _scanner
    if _scanner is None:
        settings = get_settings()
        socket_path = getattr(settings, "CLAMAV_SOCKET_PATH", None) or None
        host = getattr(settings, "CLAMAV_HOST", None) or None
        port = int(getattr(settings, "CLAMAV_PORT", 3310))
        _scanner = ClamAVScanner(socket_path=socket_path, host=host, port=port)
    return _scanner
