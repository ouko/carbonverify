import uuid
from datetime import datetime, date, timezone
from typing import List, Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    String,
    Text,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    Integer,
    ARRAY,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
)
from app.core.encrypted_types import EncryptedString
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class MethodologyEnum(str, PyEnum):
    TPDDTEC_v4 = "TPDDTEC_v4"
    VM0050 = "VM0050"
    VMR0006 = "VMR0006"
    AMS_II_G = "AMS-II.G"


class ProjectStatusEnum(str, PyEnum):
    onboarding = "onboarding"
    data_collection = "data_collection"
    calculation = "calculation"
    review = "review"
    submitted = "submitted"
    verified = "verified"
    monitoring = "monitoring"
    rejected = "rejected"


class SourceTypeEnum(str, PyEnum):
    satellite = "satellite"
    iot = "iot"
    mobile_survey = "mobile_survey"
    document = "document"
    manual_entry = "manual_entry"


class ValidationStatusEnum(str, PyEnum):
    pending = "pending"
    valid = "valid"
    flagged = "flagged"
    rejected = "rejected"


class CalculationStatusEnum(str, PyEnum):
    draft = "draft"
    review_pending = "review_pending"
    approved = "approved"
    rejected = "rejected"


class ReportStatusEnum(str, PyEnum):
    draft = "draft"
    human_review = "human_review"
    approved = "approved"
    submitted = "submitted"
    vvb_approved = "vvb_approved"
    rejected = "rejected"


class ReportTemplateTypeEnum(str, PyEnum):
    GoldStandard_TPDDTEC = "GoldStandard_TPDDTEC"
    Verra_VM0050 = "Verra_VM0050"


class QueueItemTypeEnum(str, PyEnum):
    calculation = "calculation"
    report = "report"
    vvb_response = "vvb_response"
    data_anomaly = "data_anomaly"
    agent_review = "agent_review"


class QueueStatusEnum(str, PyEnum):
    pending = "pending"
    in_review = "in_review"
    resolved = "resolved"
    escalated = "escalated"


class UserRoleEnum(str, PyEnum):
    admin = "admin"
    operator = "operator"
    developer = "developer"
    viewer = "viewer"


class FileUploadStatusEnum(str, PyEnum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DetectedFileTypeEnum(str, PyEnum):
    excel = "excel"
    csv = "csv"
    pdf = "pdf"
    image = "image"
    unknown = "unknown"


class ImageCategoryEnum(str, PyEnum):
    stove_installation = "stove_installation"
    kpt_weighing = "kpt_weighing"
    stove_condition = "stove_condition"
    enumerator_verification = "enumerator_verification"
    other = "other"


class DocumentTypeEnum(str, PyEnum):
    monitoring_report = "monitoring_report"
    kpt_results = "kpt_results"
    sales_receipt = "sales_receipt"
    survey_form = "survey_form"
    other = "other"


# ─── Kimi Claw Orchestrator Enums ─────────────────────────────────────────────

class AgentTypeEnum(str, PyEnum):
    ingestion = "ingestion"
    validation = "validation"
    calculation = "calculation"
    reporting = "reporting"
    vvb_liaison = "vvb_liaison"
    quality_control = "quality_control"
    client_success = "client_success"


class AgentStatusEnum(str, PyEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    queued_for_review = "queued_for_review"


class OrchestratorEventTypeEnum(str, PyEnum):
    state_transition = "state_transition"
    agent_dispatch = "agent_dispatch"
    agent_complete = "agent_complete"
    confidence_check = "confidence_check"
    human_review_queued = "human_review_queued"
    human_review_resolved = "human_review_resolved"
    auto_advance = "auto_advance"
    escalation = "escalation"
    error = "error"


# ─── Lead Intelligence Enums ──────────────────────────────────────────────────

class LeadRegistrySourceEnum(str, PyEnum):
    verra = "verra"
    gold_standard = "gold_standard"
    cdm = "cdm"
    kenya_national = "kenya_national"
    manual = "manual"


class LeadPriorityEnum(str, PyEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class LeadWorkflowStatusEnum(str, PyEnum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    proposal_sent = "proposal_sent"
    converted = "converted"
    dismissed = "dismissed"


class LeadProjectStatusEnum(str, PyEnum):
    under_validation = "under_validation"
    under_verification = "under_verification"
    under_certification = "under_certification"
    request_for_issuance = "request_for_issuance"
    registered = "registered"
    certified = "certified"
    rejected = "rejected"
    completed = "completed"
    unknown = "unknown"


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        Index("ix_users_role", "role"),
        Index("ix_users_created_at", "created_at"),
        Index("ix_users_email_hash", "email_hash"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(Enum(UserRoleEnum, name="user_role"), nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)  # explicit granular permissions {granted: [], revoked: []}
    password_reset_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_reset_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    developer_profile: Mapped[Optional["Developer"]] = relationship("Developer", back_populates="user", uselist=False)


class UserInvite(Base):
    __tablename__ = "user_invites"

    __table_args__ = (
        Index("ix_user_invites_token", "token"),
        Index("ix_user_invites_email_hash", "email_hash"),
        Index("ix_user_invites_expires_at", "expires_at"),
        Index("ix_user_invites_active_email", "email_hash", unique=True, postgresql_where=text("used_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(Enum(UserRoleEnum, name="user_role"), nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(EncryptedString(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="developer_profile")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="developer")


class Project(Base):
    __tablename__ = "projects"

    __table_args__ = (
        Index("ix_projects_developer_id", "developer_id"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_methodology", "methodology"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    developer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("developers.id", ondelete="CASCADE"), nullable=False)
    methodology: Mapped[MethodologyEnum] = mapped_column(
        Enum(MethodologyEnum, name="methodology"), nullable=False
    )
    crediting_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    crediting_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ProjectStatusEnum] = mapped_column(
        Enum(ProjectStatusEnum, name="project_status"), default=ProjectStatusEnum.onboarding, nullable=False
    )
    complexity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    brokerage_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tokenization_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    developer: Mapped["Developer"] = relationship("Developer", back_populates="projects")
    data_sources: Mapped[List["DataSource"]] = relationship("DataSource", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    calculation_runs: Mapped[List["CalculationRun"]] = relationship("CalculationRun", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    file_uploads: Mapped[List["FileUpload"]] = relationship("FileUpload", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    agent_runs: Mapped[List["AgentRun"]] = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    enumerators: Mapped[List["Enumerator"]] = relationship("Enumerator", back_populates="project", cascade="all, delete-orphan", passive_deletes=True)
    orchestrator_events: Mapped[List["OrchestratorEvent"]] = relationship("OrchestratorEvent", back_populates="project")


class FileUpload(Base):
    __tablename__ = "file_uploads"

    __table_args__ = (
        Index("ix_file_uploads_project_id", "project_id"),
        Index("ix_file_uploads_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    detected_type: Mapped[DetectedFileTypeEnum] = mapped_column(
        Enum(DetectedFileTypeEnum, name="detected_file_type"), nullable=False
    )
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[FileUploadStatusEnum] = mapped_column(
        Enum(FileUploadStatusEnum, name="file_upload_status"), default=FileUploadStatusEnum.uploaded, nullable=False
    )
    processing_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="file_uploads")


class DataSource(Base):
    __tablename__ = "data_sources"

    __table_args__ = (
        Index("ix_data_sources_project_id", "project_id"),
        Index("ix_data_sources_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[SourceTypeEnum] = mapped_column(
        Enum(SourceTypeEnum, name="source_type"), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    processed_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    validation_status: Mapped[ValidationStatusEnum] = mapped_column(
        Enum(ValidationStatusEnum, name="validation_status"), default=ValidationStatusEnum.pending, nullable=False
    )
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="data_sources")


class CalculationRun(Base):
    __tablename__ = "calculation_runs"

    __table_args__ = (
        Index("ix_calculation_runs_project_id", "project_id"),
        Index("ix_calculation_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    monitoring_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    monitoring_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fNRB_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emissions_reduction_tCO2e: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uncertainty_95CI: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leakage_assessment: Mapped[dict] = mapped_column(JSONB, default=dict)
    methodology_compliance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[CalculationStatusEnum] = mapped_column(
        Enum(CalculationStatusEnum, name="calculation_status"), default=CalculationStatusEnum.draft, nullable=False
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="calculation_runs")
    approver: Mapped[Optional["User"]] = relationship("User")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="calculation_run")


class Report(Base):
    __tablename__ = "reports"

    __table_args__ = (
        Index("ix_reports_project_id", "project_id"),
        Index("ix_reports_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calculation_runs.id", ondelete="CASCADE"), nullable=False)
    template_type: Mapped[ReportTemplateTypeEnum] = mapped_column(
        Enum(ReportTemplateTypeEnum, name="report_template_type"), nullable=False
    )
    draft_content: Mapped[dict] = mapped_column(JSONB, default=dict)
    final_pdf: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[ReportStatusEnum] = mapped_column(
        Enum(ReportStatusEnum, name="report_status"), default=ReportStatusEnum.draft, nullable=False
    )
    vvb_feedback: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="reports")
    calculation_run: Mapped["CalculationRun"] = relationship("CalculationRun", back_populates="reports")


class HumanReviewQueue(Base):
    __tablename__ = "human_review_queue"

    __table_args__ = (
        Index("ix_human_review_queue_assigned_to", "assigned_to"),
        Index("ix_human_review_queue_status", "status"),
        Index("ix_human_review_queue_item", "item_type", "item_id"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="check_priority_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_type: Mapped[QueueItemTypeEnum] = mapped_column(
        Enum(QueueItemTypeEnum, name="queue_item_type"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[QueueStatusEnum] = mapped_column(
        Enum(QueueStatusEnum, name="queue_status"), default=QueueStatusEnum.pending, nullable=False
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_gap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    human_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    learning_feedback: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    time_in_queue_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assignee: Mapped[Optional["User"]] = relationship("User")


# ─── Kimi Claw Orchestrator Models ────────────────────────────────────────────

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_type: Mapped[AgentTypeEnum] = mapped_column(
        Enum(AgentTypeEnum, name="agent_type"), nullable=False
    )
    status: Mapped[AgentStatusEnum] = mapped_column(
        Enum(AgentStatusEnum, name="agent_status"), default=AgentStatusEnum.pending, nullable=False
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="agent_runs")


class OrchestratorEvent(Base):
    __tablename__ = "orchestrator_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[OrchestratorEventTypeEnum] = mapped_column(
        Enum(OrchestratorEventTypeEnum, name="orchestrator_event_type"), nullable=False
    )
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    agent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="orchestrator_events")


# ─── WhatsApp Bot & Field Operations Models ───────────────────────────────────

class ConversationFlowEnum(str, PyEnum):
    survey = "survey"
    photo_collection = "photo_collection"
    support = "support"
    onboarding = "onboarding"
    idle = "idle"


class ConversationStateEnum(str, PyEnum):
    active = "active"
    completed = "completed"
    abandoned = "abandoned"
    waiting_human = "waiting_human"


class SurveyQuestionTypeEnum(str, PyEnum):
    text = "text"
    number = "number"
    choice = "choice"
    image = "image"
    location = "location"
    voice = "voice"


class Enumerator(Base):
    __tablename__ = "enumerators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    language_preference: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    data_quality_score: Mapped[Optional[float]] = mapped_column(Float, default=1.0)
    submissions_count: Mapped[int] = mapped_column(Integer, default=0)
    rejections_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))

    project: Mapped["Project"] = relationship("Project", back_populates="enumerators")


class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    phone_number: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    flow_type: Mapped[ConversationFlowEnum] = mapped_column(
        Enum(ConversationFlowEnum, name="conversation_flow"), default=ConversationFlowEnum.idle, nullable=False
    )
    state: Mapped[ConversationStateEnum] = mapped_column(
        Enum(ConversationStateEnum, name="conversation_state"), default=ConversationStateEnum.active, nullable=False
    )
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    context_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    message_history: Mapped[list] = mapped_column(JSONB, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    assigned_enumerator_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("enumerators.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id"), nullable=False)
    enumerator_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("enumerators.id"), nullable=True)
    household_id: Mapped[Optional[str]] = mapped_column(EncryptedString(100), nullable=True)
    stove_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    village_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responses: Mapped[dict] = mapped_column(JSONB, default=dict)
    photos: Mapped[list] = mapped_column(JSONB, default=list)
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_status: Mapped[ValidationStatusEnum] = mapped_column(
        Enum(ValidationStatusEnum, name="survey_validation_status"), default=ValidationStatusEnum.pending, nullable=False
    )
    validation_errors: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    submitted_via: Mapped[str] = mapped_column(String(50), default="whatsapp", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(EncryptedString(255), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))


# ─── Audit Trail ──────────────────────────────────────────────────────────────

class AuditActionEnum(str, PyEnum):
    data_ingested = "data_ingested"
    calculation_run = "calculation_run"
    report_generated = "report_generated"
    human_reviewed = "human_reviewed"
    report_approved = "report_approved"
    vvb_submitted = "vvb_submitted"
    vvb_responded = "vvb_responded"
    registry_polled = "registry_polled"
    methodology_updated = "methodology_updated"
    user_login = "user_login"
    user_logout = "user_logout"
    user_created = "user_created"
    user_updated = "user_updated"
    mfa_enabled = "mfa_enabled"
    mfa_disabled = "mfa_disabled"
    data_exported = "data_exported"
    consent_given = "consent_given"
    consent_revoked = "consent_revoked"
    dsr_received = "dsr_received"
    dsr_fulfilled = "dsr_fulfilled"
    breach_reported = "breach_reported"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_actor_id", "actor_id"),
        Index("ix_audit_logs_action_type", "action_type"),
        Index("ix_audit_logs_timestamp", "timestamp"),
        CheckConstraint("actor_type IN ('user', 'agent', 'system')", name="check_actor_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type: Mapped[AuditActionEnum] = mapped_column(
        Enum(AuditActionEnum, name="audit_action_type"), nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="user")  # user | agent | system
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # project | calculation | report | user
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    radix_tx_ref: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    actor: Mapped[Optional["User"]] = relationship("User")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_issued_at", "issued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)


# ─── Compliance ───────────────────────────────────────────────────────────────

class ConsentTypeEnum(str, PyEnum):
    data_processing = "data_processing"
    marketing = "marketing"
    third_party_sharing = "third_party_sharing"
    photo_retention = "photo_retention"
    biometric = "biometric"


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)  # phone, email, or internal ID
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)  # enumerator | household | developer
    consent_type: Mapped[ConsentTypeEnum] = mapped_column(
        Enum(ConsentTypeEnum, name="consent_type"), nullable=False
    )
    granted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    method: Mapped[str] = mapped_column(String(50), default="explicit")  # explicit | implied | verbal
    document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class DSRTypeEnum(str, PyEnum):
    access = "access"
    rectification = "rectification"
    erasure = "erasure"
    restriction = "restriction"
    portability = "portability"
    objection = "objection"


class DSRStatusEnum(str, PyEnum):
    received = "received"
    under_review = "under_review"
    in_progress = "in_progress"
    fulfilled = "fulfilled"
    rejected = "rejected"
    escalated = "escalated"


class DataSubjectRequest(Base):
    __tablename__ = "data_subject_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type: Mapped[DSRTypeEnum] = mapped_column(
        Enum(DSRTypeEnum, name="dsr_type"), nullable=False
    )
    status: Mapped[DSRStatusEnum] = mapped_column(
        Enum(DSRStatusEnum, name="dsr_status"), default=DSRStatusEnum.received, nullable=False
    )
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfillment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class BreachStatusEnum(str, PyEnum):
    detected = "detected"
    under_investigation = "under_investigation"
    contained = "contained"
    notified_regulator = "notified_regulator"
    notified_subjects = "notified_subjects"
    resolved = "resolved"


class BreachNotification(Base):
    __tablename__ = "breach_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # low | medium | high | critical
    status: Mapped[BreachStatusEnum] = mapped_column(
        Enum(BreachStatusEnum, name="breach_status"), default=BreachStatusEnum.detected, nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    detected_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    affected_subjects_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    affected_data_types: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    containment_measures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    regulator_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    subjects_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ConflictOfInterest(Base):
    __tablename__ = "conflicts_of_interest"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)  # financial | familial | employment | other
    description: Mapped[str] = mapped_column(Text, nullable=False)
    disclosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ─── Methodology Versioning ───────────────────────────────────────────────────

class MethodologyVersion(Base):
    __tablename__ = "methodology_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    methodology_name: Mapped[str] = mapped_column(String(100), nullable=False)  # TPDDTEC_v4, VM0050, etc.
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("methodology_name", "version", name="uq_methodology_version"),
    )


# ─── Brokerage & Tokenization ─────────────────────────────────────────────────

class ListingStatusEnum(str, PyEnum):
    draft = "draft"
    active = "active"
    sold = "sold"
    withdrawn = "withdrawn"


class TradeTypeEnum(str, PyEnum):
    spot = "spot"
    forward = "forward"
    escrow = "escrow"


class TransactionStatusEnum(str, PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    in_escrow = "in_escrow"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class BuyerTypeEnum(str, PyEnum):
    corporate = "corporate"
    retailer = "retailer"
    offset_seeker = "offset_seeker"
    wholesaler = "wholesaler"


class BrokerageListing(Base):
    __tablename__ = "brokerage_listings"

    __table_args__ = (
        Index("ix_brokerage_listings_seller_id", "seller_id"),
        Index("ix_brokerage_listings_project_id", "project_id"),
        Index("ix_brokerage_listings_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    available_credits: Mapped[float] = mapped_column(Float, nullable=False)
    price_per_credit_usd: Mapped[float] = mapped_column(Float, nullable=False)
    vintage_year: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology: Mapped[str] = mapped_column(String(100), nullable=False)
    co_benefits: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    delivery_timeline_days: Mapped[int] = mapped_column(Integer, default=30)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[ListingStatusEnum] = mapped_column(
        Enum(ListingStatusEnum, name="listing_status"), default=ListingStatusEnum.draft, nullable=False
    )
    minimum_purchase: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    project: Mapped["Project"] = relationship("Project")
    seller: Mapped["User"] = relationship("User")


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"

    __table_args__ = (
        Index("ix_buyer_profiles_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    buyer_type: Mapped[BuyerTypeEnum] = mapped_column(
        Enum(BuyerTypeEnum, name="buyer_type"), nullable=False
    )
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_methodologies: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    price_range_min_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_range_max_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preferred_locations: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    delivery_timeline_preference_days: Mapped[int] = mapped_column(Integer, default=90)
    auto_match_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user: Mapped["User"] = relationship("User")


class TradeMatch(Base):
    __tablename__ = "trade_matches"

    __table_args__ = (
        Index("ix_trade_matches_listing_id", "listing_id"),
        Index("ix_trade_matches_buyer_id", "buyer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokerage_listings.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    methodology_match: Mapped[bool] = mapped_column(Boolean, default=False)
    price_match: Mapped[bool] = mapped_column(Boolean, default=False)
    location_match: Mapped[bool] = mapped_column(Boolean, default=False)
    timeline_match: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="suggested", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    listing: Mapped["BrokerageListing"] = relationship("BrokerageListing")
    buyer: Mapped["User"] = relationship("User")


class BrokerageTransaction(Base):
    __tablename__ = "brokerage_transactions"

    __table_args__ = (
        Index("ix_brokerage_transactions_listing_id", "listing_id"),
        Index("ix_brokerage_transactions_buyer_id", "buyer_id"),
        Index("ix_brokerage_transactions_seller_id", "seller_id"),
        Index("ix_brokerage_transactions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokerage_listings.id"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    trade_type: Mapped[TradeTypeEnum] = mapped_column(
        Enum(TradeTypeEnum, name="trade_type"), nullable=False
    )
    credits_amount: Mapped[float] = mapped_column(Float, nullable=False)
    price_per_credit_usd: Mapped[float] = mapped_column(Float, nullable=False)
    total_value_usd: Mapped[float] = mapped_column(Float, nullable=False)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.025)
    commission_usd: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[TransactionStatusEnum] = mapped_column(
        Enum(TransactionStatusEnum, name="transaction_status"), default=TransactionStatusEnum.pending, nullable=False
    )
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    escrow_release_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vvb_certificate_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    listing: Mapped["BrokerageListing"] = relationship("BrokerageListing")
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])


class Escrow(Base):
    __tablename__ = "escrows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokerage_transactions.id"), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    buyer_deposited: Mapped[bool] = mapped_column(Boolean, default=False)
    seller_transferred: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="holding", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped["BrokerageTransaction"] = relationship("BrokerageTransaction")


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokerage_transactions.id"), nullable=False)
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    invoiced: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    transaction: Mapped["BrokerageTransaction"] = relationship("BrokerageTransaction")


# ─── Tokenization ─────────────────────────────────────────────────────────────

class TokenStatusEnum(str, PyEnum):
    minted = "minted"
    listed = "listed"
    sold = "sold"
    retired = "retired"
    fractional = "fractional"


class CarbonCreditToken(Base):
    __tablename__ = "carbon_credit_tokens"

    __table_args__ = (
        Index("ix_carbon_credit_tokens_project_id", "project_id"),
        Index("ix_carbon_credit_tokens_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calculation_runs.id"), nullable=False)
    tonnes_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    vintage_year: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology: Mapped[str] = mapped_column(String(100), nullable=False)
    vvb_registry: Mapped[str] = mapped_column(String(100), nullable=False)
    vvb_certificate_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radix_token_address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    radix_resource_address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[TokenStatusEnum] = mapped_column(
        Enum(TokenStatusEnum, name="token_status"), default=TokenStatusEnum.minted, nullable=False
    )
    is_fractional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_token_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    project: Mapped["Project"] = relationship("Project")
    calculation_run: Mapped["CalculationRun"] = relationship("CalculationRun")


class TokenListing(Base):
    __tablename__ = "token_listings"

    __table_args__ = (
        Index("ix_token_listings_token_id", "token_id"),
        Index("ix_token_listings_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carbon_credit_tokens.id"), nullable=False)
    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    price_per_tonne_usd: Mapped[float] = mapped_column(Float, nullable=False)
    amount_available: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    token: Mapped["CarbonCreditToken"] = relationship("CarbonCreditToken")
    seller: Mapped["User"] = relationship("User")


class TokenRetirement(Base):
    __tablename__ = "token_retirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carbon_credit_tokens.id"), nullable=False)
    retired_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tonnes_retired: Mapped[float] = mapped_column(Float, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    beneficiary_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    beneficiary_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    radix_burn_tx_ref: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    retirement_certificate_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    token: Mapped["CarbonCreditToken"] = relationship("CarbonCreditToken")
    retiree: Mapped["User"] = relationship("User")


class CorporatePortfolio(Base):
    __tablename__ = "corporate_portfolios"

    __table_args__ = (
        Index("ix_corporate_portfolios_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    total_credits_held: Mapped[float] = mapped_column(Float, default=0.0)
    total_credits_retired: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_value_usd: Mapped[float] = mapped_column(Float, default=0.0)
    esg_report_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship("User")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    __table_args__ = (
        Index("ix_portfolio_holdings_portfolio_id", "portfolio_id"),
        Index("ix_portfolio_holdings_token_id", "token_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("corporate_portfolios.id"), nullable=False)
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carbon_credit_tokens.id"), nullable=False)
    tonnes_held: Mapped[float] = mapped_column(Float, nullable=False)
    tonnes_retired: Mapped[float] = mapped_column(Float, default=0.0)
    acquisition_price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    portfolio: Mapped["CorporatePortfolio"] = relationship("CorporatePortfolio")
    token: Mapped["CarbonCreditToken"] = relationship("CarbonCreditToken")


# ─── Lead Intelligence ──────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    __table_args__ = (
        Index("ix_leads_registry_source", "registry_source"),
        Index("ix_leads_status", "status"),
        Index("ix_leads_priority", "priority"),
        Index("ix_leads_stuck_score", "stuck_score"),
        Index("ix_leads_lead_status", "lead_status"),
        Index("ix_leads_country", "country"),
        Index("ix_leads_assigned_to", "assigned_to"),
        Index("ix_leads_external_id", "external_id"),
        Index("ix_leads_scraped_at", "scraped_at"),
        UniqueConstraint("registry_source", "external_id", name="uq_lead_registry_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registry_source: Mapped[LeadRegistrySourceEnum] = mapped_column(
        Enum(LeadRegistrySourceEnum, name="lead_registry_source"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    project_developer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    developer_contact: Mapped[Optional[str]] = mapped_column(EncryptedString(500), nullable=True)
    developer_email: Mapped[Optional[str]] = mapped_column(EncryptedString(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location_coords: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    methodology: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[LeadProjectStatusEnum] = mapped_column(
        Enum(LeadProjectStatusEnum, name="lead_project_status"), default=LeadProjectStatusEnum.unknown, nullable=False
    )
    crediting_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    crediting_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_verification_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_monitoring_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_credits_per_year: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    registry_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    days_in_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stuck_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    priority: Mapped[LeadPriorityEnum] = mapped_column(
        Enum(LeadPriorityEnum, name="lead_priority"), default=LeadPriorityEnum.low, nullable=False
    )
    lead_status: Mapped[LeadWorkflowStatusEnum] = mapped_column(
        Enum(LeadWorkflowStatusEnum, name="lead_workflow_status"), default=LeadWorkflowStatusEnum.new, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    assignee: Mapped[Optional["User"]] = relationship("User")


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="demo", nullable=False)  # live, demo, error
    data_source: Mapped[str] = mapped_column(String(20), default="demo", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="demo", nullable=False)
