"""Tests for ClamAV scanner with mocked clamd."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.clamav_scanner import ClamAVScanner, ScanStatus, ScanResult


class TestClamAVScanner:
    def test_ping_success(self):
        scanner = ClamAVScanner()
        mock_client = MagicMock()
        scanner._client = mock_client
        assert scanner.ping() is True
        mock_client.ping.assert_called_once()

    def test_ping_no_client(self):
        scanner = ClamAVScanner()
        assert scanner.ping() is False

    def test_scan_clean(self):
        scanner = ClamAVScanner()
        mock_client = MagicMock()
        mock_client.instream.return_value = {"stream": ("OK", None)}
        scanner._client = mock_client

        result = scanner._scan_sync(b"clean data")
        assert result.status == ScanStatus.clean
        assert result.signature is None

    def test_scan_infected(self):
        scanner = ClamAVScanner()
        mock_client = MagicMock()
        mock_client.instream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
        scanner._client = mock_client

        result = scanner._scan_sync(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
        assert result.status == ScanStatus.infected
        assert result.signature == "Eicar-Test-Signature"

    def test_scan_error_unexpected_response(self):
        scanner = ClamAVScanner()
        mock_client = MagicMock()
        mock_client.instream.return_value = {"stream": ("UNKNOWN", None)}
        scanner._client = mock_client

        result = scanner._scan_sync(b"data")
        assert result.status == ScanStatus.error

    def test_scan_error_client_unavailable(self):
        scanner = ClamAVScanner()
        with patch.object(scanner, "_get_client", return_value=None):
            result = scanner._scan_sync(b"data")
        assert result.status == ScanStatus.error
        assert "ClamAV not available" in (result.message or "")

    @pytest.mark.asyncio
    async def test_scan_buffer_async(self):
        scanner = ClamAVScanner()
        mock_client = MagicMock()
        mock_client.instream.return_value = {"stream": ("OK", None)}
        scanner._client = mock_client

        result = await scanner.scan_buffer(b"async clean data")
        assert result.status == ScanStatus.clean
