import uuid
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    Integer,
    JSON,
    ARRAY,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class MethodologyEnum(str, Enum):
    TPDDTEC_v4 = "TPDDTEC_v4"
    VM0050 = "VM0050"
    VMR0006 = "VMR0006"
    AMS_II_G = "AMS-II.G"


class ProjectStatusEnum(str, Enum):
    onboarding = "onboarding"
    data_collection = "data_collection"
    calculation = "calculation"
    review = "review"
    submitted = "submitted"
    verified = "verified"
    monitoring = "monitoring"


class SourceTypeEnum(str, Enum):
    satellite = "satellite"
    iot = "iot"
    mobile_survey = "mobile_survey"
    document = "document"
    manual_entry = "manual_entry"


class ValidationStatusEnum(str, Enum):
    pending = "pending"
    valid = "valid"
    flagged = "flagged"
    rejected = "rejected"


class CalculationStatusEnum(str, Enum):
    draft = "draft"
    review_pending = "review_pending"
    approved = "approved"
    rejected = "rejected"


class ReportStatusEnum(str, Enum):
    draft = "draft"
    human_review = "human_review"
    approved = "approved"
    submitted = "submitted"
    vvb_approved = "vvb_approved"
    rejected = "rejected"


class ReportTemplateTypeEnum(str, Enum):
    GoldStandard_TPDDTEC = "GoldStandard_TPDDTEC"
    Verra_VM0050 = "Verra_VM0050"


class QueueItemTypeEnum(str, Enum):
    calculation = "calculation"
    report = "report"
    vvb_response = "vvb_response"
    data_anomaly = "data_anomaly"


class QueueStatusEnum(str, Enum):
    pending = "pending"
    in_review = "in_review"
    resolved = "resolved"
    escalated = "escalated"


class UserRoleEnum(str, Enum):
    admin = "admin"
    operator = "operator"
    developer = "developer"
    viewer = "viewer"


class FileUploadStatusEnum(str, Enum):
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DetectedFileTypeEnum(str, Enum):
    excel = "excel"
    csv = "csv"
    pdf = "pdf"
    image = "image"
    unknown = "unknown"


class ImageCategoryEnum(str, Enum):
    stove_installation = "stove_installation"
    kpt_weighing = "kpt_weighing"
    stove_condition = "stove_condition"
    enumerator_verification = "enumerator_verification"
    other = "other"


class DocumentTypeEnum(str, Enum):
    monitoring_report = "monitoring_report"
    kpt_results = "kpt_results"
    sales_receipt = "sales_receipt"
    survey_form = "survey_form"
    other = "other"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(Enum(UserRoleEnum, name="user_role"), nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    developer_profile: Mapped[Optional["Developer"]] = relationship("Developer", back_populates="user", uselist=False)


class Developer(Base):
    __tablename__ = "developers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="developer_profile")
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="developer")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    developer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("developers.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    developer: Mapped["Developer"] = relationship("Developer", back_populates="projects")
    data_sources: Mapped[List["DataSource"]] = relationship("DataSource", back_populates="project")
    calculation_runs: Mapped[List["CalculationRun"]] = relationship("CalculationRun", back_populates="project")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="project")
    file_uploads: Mapped[List["FileUpload"]] = relationship("FileUpload", back_populates="project")


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="file_uploads")


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="data_sources")


class CalculationRun(Base):
    __tablename__ = "calculation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
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
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="calculation_runs")
    approver: Mapped[Optional["User"]] = relationship("User")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="calculation_run")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calculation_runs.id"), nullable=False)
    template_type: Mapped[ReportTemplateTypeEnum] = mapped_column(
        Enum(ReportTemplateTypeEnum, name="report_template_type"), nullable=False
    )
    draft_content: Mapped[dict] = mapped_column(JSONB, default=dict)
    final_pdf: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[ReportStatusEnum] = mapped_column(
        Enum(ReportStatusEnum, name="report_status"), default=ReportStatusEnum.draft, nullable=False
    )
    vvb_feedback: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project", back_populates="reports")
    calculation_run: Mapped["CalculationRun"] = relationship("CalculationRun", back_populates="reports")


class HumanReviewQueue(Base):
    __tablename__ = "human_review_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_type: Mapped[QueueItemTypeEnum] = mapped_column(
        Enum(QueueItemTypeEnum, name="queue_item_type"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[QueueStatusEnum] = mapped_column(
        Enum(QueueStatusEnum, name="queue_status"), default=QueueStatusEnum.pending, nullable=False
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    assignee: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="check_priority_range"),
    )
