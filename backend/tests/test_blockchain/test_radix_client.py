import pytest

from app.blockchain.radix_client import RadixClient, AuditTrailAnchor


class TestRadixClient:
    def test_compute_hash_consistency(self):
        client = RadixClient()
        data = {"key": "value", "number": 42}
        h1 = client._compute_hash(data)
        h2 = client._compute_hash(data)
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_hash_different_data(self):
        client = RadixClient()
        h1 = client._compute_hash({"a": 1})
        h2 = client._compute_hash({"a": 2})
        assert h1 != h2

    def test_build_manifest_contains_hash(self):
        client = RadixClient()
        client.account_address = "account_rdx123"
        manifest = client._build_manifest("abc123", "test memo")
        assert "abc123" in manifest
        assert "test memo" in manifest
        assert "CALL_METHOD" in manifest

    @pytest.mark.asyncio
    async def test_anchor_audit_log_disabled(self):
        """In disabled mode, should return simulated tx ref."""
        client = RadixClient()
        client.enabled = False
        data = {"test": "value"}
        result = await client.anchor_audit_log(data, memo="test")
        assert result.success is True
        assert result.tx_ref is not None
        assert result.data_hash is not None
        assert len(result.data_hash) == 64

    @pytest.mark.asyncio
    async def test_verify_anchor_disabled(self):
        client = RadixClient()
        client.enabled = False
        data = {"test": "value"}
        anchor_result = await client.anchor_audit_log(data)
        verified = await client.verify_anchor(anchor_result.tx_ref, data)
        assert verified is True

    @pytest.mark.asyncio
    async def test_verify_anchor_wrong_data(self):
        client = RadixClient()
        client.enabled = False
        data = {"test": "value"}
        anchor_result = await client.anchor_audit_log(data)
        verified = await client.verify_anchor(anchor_result.tx_ref, {"test": "wrong"})
        assert verified is False

    @pytest.mark.asyncio
    async def test_get_transaction_status_disabled(self):
        client = RadixClient()
        client.enabled = False
        status = await client.get_transaction_status("tx123")
        assert status["status"] == "simulated"


class TestAuditTrailAnchor:
    @pytest.mark.asyncio
    async def test_anchor_calculation_run(self):
        anchor = AuditTrailAnchor()
        anchor.client.enabled = False
        result = await anchor.anchor_calculation_run(
            calculation_run_id=__import__("uuid").uuid4(),
            input_data={"fnrb": 0.42},
            output_data={"emissions": 1500.5},
        )
        assert result.success is True
        assert result.tx_ref is not None

    @pytest.mark.asyncio
    async def test_anchor_report_approval(self):
        anchor = AuditTrailAnchor()
        anchor.client.enabled = False
        result = await anchor.anchor_report_approval(
            report_id=__import__("uuid").uuid4(),
            approver_id=__import__("uuid").uuid4(),
            report_hash="abc" * 20,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify(self):
        anchor = AuditTrailAnchor()
        anchor.client.enabled = False
        data = {"type": "test", "value": 123}
        tx_ref = await anchor.client.anchor_audit_log(data)
        verified = await anchor.verify(tx_ref.tx_ref, data)
        assert verified is True
