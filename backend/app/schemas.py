import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ─── Shared ───────────────────────────────────────────────────────────────────

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Users ────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str
    mfa_enabled: bool = False


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserOut(UserBase, ORMBase):
    id: uuid.UUID
    created_at: datetime


class UserInDB(UserOut):
    hashed_password: str


# ─── Developers ───────────────────────────────────────────────────────────────

class DeveloperBase(BaseModel):
    company_name: str
    contact_phone: Optional[str] = None
    location: Optional[str] = None


class DeveloperCreate(DeveloperBase):
    user_id: uuid.UUID


class DeveloperOut(DeveloperBase, ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID


# ─── Projects ─────────────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    name: str
    methodology: str
    crediting_period_start: date
    crediting_period_end: date
    status: Optional[str] = "onboarding"
    complexity_score: Optional[float] = None
    confidence_threshold: float = 0.85


class ProjectCreate(ProjectBase):
    developer_id: uuid.UUID


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    complexity_score: Optional[float] = None
    confidence_threshold: Optional[float] = None


class ProjectOut(ProjectBase, ORMBase):
    id: uuid.UUID
    developer_id: uuid.UUID
    created_at: datetime


# ─── File Uploads ─────────────────────────────────────────────────────────────

class FileUploadOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    original_filename: str
    detected_type: str
    mime_type: str
    s3_key: str
    s3_bucket: str
    file_size_bytes: int
    file_hash_sha256: str
    status: str
    processing_result: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    processed_at: Optional[datetime] = None


class FileUploadResponse(BaseModel):
    file_id: uuid.UUID
    detected_type: str
    mime_type: str
    status: str
    s3_key: str
    file_size_bytes: int
    file_hash_sha256: str
    message: str


# ─── Data Sources ─────────────────────────────────────────────────────────────

class DataSourceBase(BaseModel):
    source_type: str
    schema_version: str
    raw_data: Dict[str, Any] = {}
    processed_data: Dict[str, Any] = {}
    validation_status: Optional[str] = "pending"
    validation_errors: Optional[List[str]] = None
    provenance: Dict[str, Any] = {}


class DataSourceCreate(DataSourceBase):
    project_id: uuid.UUID


class DataSourceUpdate(BaseModel):
    validation_status: Optional[str] = None
    validation_errors: Optional[List[str]] = None
    processed_data: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None


class DataSourceOut(DataSourceBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    confidence_score: Optional[float] = None
    created_at: datetime


# ─── Calculation Runs ─────────────────────────────────────────────────────────

class CalculationRunBase(BaseModel):
    monitoring_period_start: date
    monitoring_period_end: date
    fNRB_value: Optional[float] = None
    emissions_reduction_tCO2e: Optional[float] = None
    uncertainty_95CI: Optional[float] = None
    leakage_assessment: Dict[str, Any] = {}
    methodology_compliance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    status: Optional[str] = "draft"


class CalculationRunCreate(CalculationRunBase):
    project_id: uuid.UUID


class CalculationRunUpdate(BaseModel):
    fNRB_value: Optional[float] = None
    emissions_reduction_tCO2e: Optional[float] = None
    uncertainty_95CI: Optional[float] = None
    leakage_assessment: Optional[Dict[str, Any]] = None
    methodology_compliance_score: Optional[float] = None
    confidence_score: Optional[float] = None
    status: Optional[str] = None
    approved_by: Optional[uuid.UUID] = None


class CalculationRunOut(CalculationRunBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    approved_by: Optional[uuid.UUID] = None
    created_at: datetime


# ─── Reports ──────────────────────────────────────────────────────────────────

class ReportBase(BaseModel):
    template_type: str
    draft_content: Dict[str, Any] = {}
    final_pdf: Optional[str] = None
    status: Optional[str] = "draft"
    vvb_feedback: Optional[Dict[str, Any]] = None


class ReportCreate(ReportBase):
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID


class ReportUpdate(BaseModel):
    draft_content: Optional[Dict[str, Any]] = None
    final_pdf: Optional[str] = None
    status: Optional[str] = None
    vvb_feedback: Optional[Dict[str, Any]] = None


class ReportOut(ReportBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID
    created_at: datetime


# ─── Human Review Queue ───────────────────────────────────────────────────────

class HumanReviewQueueBase(BaseModel):
    item_type: str
    item_id: uuid.UUID
    reason: str
    priority: int = Field(..., ge=1, le=5)
    status: Optional[str] = "pending"
    resolution_notes: Optional[str] = None


class HumanReviewQueueCreate(HumanReviewQueueBase):
    assigned_to: Optional[uuid.UUID] = None


class HumanReviewQueueUpdate(BaseModel):
    assigned_to: Optional[uuid.UUID] = None
    status: Optional[str] = None
    resolution_notes: Optional[str] = None


class HumanReviewQueueOut(HumanReviewQueueBase, ORMBase):
    id: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None


# ─── IoT Webhook ──────────────────────────────────────────────────────────────

class IoTWebhookPayload(BaseModel):
    device_id: str
    timestamp: datetime
    stove_id: Optional[str] = None
    cooking_events: Optional[int] = None
    total_cooking_minutes: Optional[float] = None
    temperature_avg: Optional[float] = None
    usage_status: Optional[str] = None
    raw_payload: Dict[str, Any] = {}


class IoTWebhookResponse(BaseModel):
    received: bool
    data_source_id: Optional[uuid.UUID] = None
    validation_status: str
    confidence_score: Optional[float] = None
    errors: Optional[List[str]] = None


# ─── Auth ─────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    type: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthCheck(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: datetime


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_projects: int
    projects_by_status: Dict[str, int]
    pending_reviews: int
    recent_calculations: int
    total_emissions_reduced: float


# ─── WhatsApp Bot Schemas ─────────────────────────────────────────────────────

class EnumeratorCreate(BaseModel):
    project_id: uuid.UUID
    name: str
    phone_number: str
    language_preference: str = "en"


class EnumeratorOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    phone_number: str
    language_preference: str
    active: bool
    data_quality_score: Optional[float]
    submissions_count: int
    rejections_count: int
    last_sync_at: Optional[datetime]
    created_at: datetime


class SurveyResponseOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: uuid.UUID
    enumerator_id: Optional[uuid.UUID]
    household_id: Optional[str]
    stove_id: Optional[str]
    village_name: Optional[str]
    responses: Dict[str, Any]
    gps_latitude: Optional[float]
    gps_longitude: Optional[float]
    validation_status: str
    confidence_score: Optional[float]
    submitted_via: str
    created_at: datetime


class SupportTicketOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    phone_number: str
    issue_type: str
    description: str
    status: str
    assigned_to: Optional[uuid.UUID]
    created_at: datetime
    resolved_at: Optional[datetime]


class WhatsAppMessageIn(BaseModel):
    phone_number: str
    message: str
    message_type: str = "text"
