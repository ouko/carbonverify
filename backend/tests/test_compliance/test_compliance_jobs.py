import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from sqlalchemy import select

from app.tasks.compliance_jobs import (
    _erase_enumerator,
    _erase_user,
    _erase_household,
    _erase_developer,
    _mark_dsr_rejected,
    ANONYMIZED_ACTOR_ID,
)
from app.models import (
    DataSubjectRequest,
    DSRStatusEnum,
    Enumerator,
    SurveyResponse,
    WhatsAppConversation,
    SupportTicket,
    HumanReviewQueue,
    RefreshToken,
    UserInvite,
    BuyerProfile,
    ConflictOfInterest,
    Developer,
    AuditLog,
    User,
    DSRTypeEnum,
    QueueItemTypeEnum,
    QueueStatusEnum,
    AuditActionEnum,
)


class TestEraseEnumerator:
    @pytest.mark.asyncio
    async def test_uses_assigned_enumerator_id(self, db_session):
        """Verify the fix for invalid column reference (enumerator_id -> assigned_enumerator_id)."""
        project_id = uuid.uuid4()
        enum_id = uuid.uuid4()

        enum = Enumerator(
            id=enum_id,
            project_id=project_id,
            name="Test Enum",
            phone_number="+254700000001",
        )
        conv = WhatsAppConversation(
            id=uuid.uuid4(),
            project_id=project_id,
            phone_number="+254700000001",
            assigned_enumerator_id=enum_id,
        )
        resp = SurveyResponse(
            id=uuid.uuid4(),
            project_id=project_id,
            conversation_id=conv.id,
            enumerator_id=enum_id,
            photos=["s3://bucket/key1.jpg", {"s3_key": "key2.jpg"}],
        )

        db_session.add_all([enum, conv, resp])
        await db_session.commit()

        with patch("app.tasks.compliance_jobs.boto3") as mock_boto:
            mock_s3 = MagicMock()
            mock_boto.client.return_value = mock_s3
            await _erase_enumerator(db_session, str(enum_id))

        # Verify conversation was deleted using assigned_enumerator_id
        result = await db_session.execute(
            select(WhatsAppConversation).where(WhatsAppConversation.id == conv.id)
        )
        assert result.scalar_one_or_none() is None

        # Verify survey response deleted
        result = await db_session.execute(
            select(SurveyResponse).where(SurveyResponse.id == resp.id)
        )
        assert result.scalar_one_or_none() is None

        # Verify enumerator deleted
        result = await db_session.execute(
            select(Enumerator).where(Enumerator.id == enum_id)
        )
        assert result.scalar_one_or_none() is None

        # Verify S3 deletion was attempted
        assert mock_s3.delete_object.call_count == 2


class TestEraseUser:
    @pytest.mark.asyncio
    async def test_complete_user_erasure(self, db_session):
        """Verify all user-related records are deleted/redacted."""
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()
        future = datetime.now(timezone.utc) + timedelta(days=365)

        user = User(
            id=user_id,
            email="test@example.com",
            email_hash="hash",
            name="Test User",
            role="viewer",
            hashed_password="secret",
            is_active=True,
        )

        refresh = RefreshToken(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash="hash1",
            expires_at=future,
        )

        invite = UserInvite(
            id=uuid.uuid4(),
            token="token1",
            email="invited@example.com",
            email_hash="hash2",
            name="Invited",
            role="viewer",
            invited_by=user_id,
            expires_at=future,
        )

        buyer = BuyerProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            buyer_type="corporate",
        )

        coi = ConflictOfInterest(
            id=uuid.uuid4(),
            user_id=user_id,
            project_id=project_id,
            relationship_type="financial",
            description="test",
        )

        hrq = HumanReviewQueue(
            id=uuid.uuid4(),
            item_type=QueueItemTypeEnum.report,
            item_id=project_id,
            reason="test",
            priority=1,
            assigned_to=user_id,
            status=QueueStatusEnum.pending,
        )

        ticket = SupportTicket(
            id=uuid.uuid4(),
            project_id=project_id,
            conversation_id=uuid.uuid4(),
            phone_number="+254700000001",
            issue_type="bug",
            description="test",
            assigned_to=user_id,
        )

        audit = AuditLog(
            id=uuid.uuid4(),
            action_type=AuditActionEnum.user_login,
            actor_id=user_id,
            actor_type="user",
            target_type="user",
        )

        developer = Developer(
            id=uuid.uuid4(),
            user_id=user_id,
            company_name="Acme Corp",
            contact_phone="+254700000002",
        )

        db_session.add_all([user, refresh, invite, buyer, coi, hrq, ticket, audit, developer])
        await db_session.commit()

        with patch("app.tasks.compliance_jobs.SessionManager") as mock_session_mgr:
            mock_session_mgr.destroy_all_user_sessions = AsyncMock(return_value=1)
            await _erase_user(db_session, str(user_id))

        # Verify user is redacted and deactivated
        result = await db_session.execute(select(User).where(User.id == user_id))
        updated_user = result.scalar_one()
        assert updated_user.is_active is False
        assert updated_user.hashed_password == ""
        assert updated_user.name == "Redacted User"
        assert "redacted" in updated_user.email

        # Verify refresh tokens deleted
        result = await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
        assert result.scalar_one_or_none() is None

        # Verify invites deleted
        result = await db_session.execute(select(UserInvite).where(UserInvite.invited_by == user_id))
        assert result.scalar_one_or_none() is None

        # Verify buyer profile deleted
        result = await db_session.execute(select(BuyerProfile).where(BuyerProfile.user_id == user_id))
        assert result.scalar_one_or_none() is None

        # Verify COI deleted
        result = await db_session.execute(select(ConflictOfInterest).where(ConflictOfInterest.user_id == user_id))
        assert result.scalar_one_or_none() is None

        # Verify HRQ unassigned
        result = await db_session.execute(select(HumanReviewQueue).where(HumanReviewQueue.id == hrq.id))
        updated_hrq = result.scalar_one()
        assert updated_hrq.assigned_to is None

        # Verify ticket unassigned
        result = await db_session.execute(select(SupportTicket).where(SupportTicket.id == ticket.id))
        updated_ticket = result.scalar_one()
        assert updated_ticket.assigned_to is None

        # Verify audit log anonymized
        result = await db_session.execute(select(AuditLog).where(AuditLog.id == audit.id))
        updated_audit = result.scalar_one()
        assert updated_audit.actor_id == ANONYMIZED_ACTOR_ID

        # Verify developer profile redacted
        result = await db_session.execute(select(Developer).where(Developer.id == developer.id))
        updated_dev = result.scalar_one()
        assert updated_dev.company_name == ""
        assert updated_dev.contact_phone == ""

        # Verify Redis sessions cleared
        mock_session_mgr.destroy_all_user_sessions.assert_awaited_once_with(str(user_id))


class TestMarkDSRRejected:
    @pytest.mark.asyncio
    async def test_mark_dsr_rejected(self, db_session):
        """Verify _mark_dsr_rejected sets status and rejection_reason."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        dsr = DataSubjectRequest(
            id=uuid.uuid4(),
            request_type=DSRTypeEnum.erasure,
            status=DSRStatusEnum.in_progress,
            subject_id="sub-123",
            subject_type="user",
            sla_deadline=future,
        )
        db_session.add(dsr)
        await db_session.commit()

        # Patch AsyncSessionLocal so _mark_dsr_rejected uses the test session
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.compliance_jobs.AsyncSessionLocal", return_value=mock_session_ctx):
            await _mark_dsr_rejected(str(dsr.id), "something went wrong")

        result = await db_session.execute(select(DataSubjectRequest).where(DataSubjectRequest.id == dsr.id))
        updated = result.scalar_one()
        assert updated.status == DSRStatusEnum.rejected
        assert updated.rejection_reason == "something went wrong"
