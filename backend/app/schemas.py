import uuid
import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from enum import Enum as PyEnum
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

from app.models import SourceTypeEnum


# ─── Shared ───────────────────────────────────────────────────────────────────

class SubjectTypeEnum(str, PyEnum):
    enumerator = "enumerator"
    household = "household"
    developer = "developer"
    user = "user"


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Users ────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str
    mfa_enabled: bool = False


class UserCreate(UserBase):
    password: str = Field(..., min_length=12)

    @field_validator("password")
    @classmethod
    def _validate_password_complexity(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain at least one special character (@$!%*?&)")
        return v


class UserCreateByAdmin(BaseModel):
    email: EmailStr
    name: str
    role: str
    password: str = Field(..., min_length=12)
    mfa_enabled: bool = False

    @field_validator("password")
    @classmethod
    def _validate_password_complexity(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain at least one special character (@$!%*?&)")
        return v


class UserUpdateByAdmin(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    mfa_enabled: Optional[bool] = None


class UserOut(UserBase, ORMBase):
    id: uuid.UUID
    is_active: bool
    permissions: dict
    created_at: datetime


class UserDetailOut(UserOut):
    last_login_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None


class UserInDB(UserOut):
    hashed_password: str


class UserInviteCreate(BaseModel):
    email: EmailStr
    name: str
    role: str = "viewer"
    permissions: List[str] = []


class UserInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    token: str
    email: str
    name: str
    role: str
    expires_at: datetime
    created_at: datetime
    used_at: Optional[datetime] = None


class InviteAcceptRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=12)
    name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _validate_password_complexity(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain at least one special character (@$!%*?&)")
        return v


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

    @model_validator(mode='after')
    def check_dates(self):
        if self.crediting_period_start and self.crediting_period_end:
            if self.crediting_period_end <= self.crediting_period_start:
                raise ValueError("crediting_period_end must be after crediting_period_start")
        return self


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    complexity_score: Optional[float] = None
    confidence_threshold: Optional[float] = None
    brokerage_enabled: Optional[bool] = None
    tokenization_enabled: Optional[bool] = None
    crediting_period_start: Optional[date] = None
    crediting_period_end: Optional[date] = None

    @model_validator(mode='after')
    def check_dates(self):
        if self.crediting_period_start and self.crediting_period_end:
            if self.crediting_period_end <= self.crediting_period_start:
                raise ValueError("crediting_period_end must be after crediting_period_start")
        return self


class ProjectOut(ProjectBase, ORMBase):
    id: uuid.UUID
    developer_id: uuid.UUID
    brokerage_enabled: bool = False
    tokenization_enabled: bool = False
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
    source_type: SourceTypeEnum
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
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    session_id: Optional[str] = None


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    type: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MFAVerifyRequest(BaseModel):
    temp_token: str
    totp_code: str


class MFAConfirmResponse(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    mfa_enabled: bool = False
    backup_codes: List[str] = []


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12)

    @field_validator("new_password")
    @classmethod
    def _validate_password_complexity(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[@$!%*?&]", v):
            raise ValueError("Password must contain at least one special character (@$!%*?&)")
        return v


# ─── API Keys ─────────────────────────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: List[str] = []
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list
    created_by: uuid.UUID
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime


class ApiKeyCreateResponse(ApiKeyOut):
    key: str


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


# ─── Brokerage Schemas ────────────────────────────────────────────────────────

class BrokerageListingCreate(BaseModel):
    project_id: uuid.UUID
    available_credits: float = Field(..., gt=0)
    price_per_credit_usd: float = Field(..., gt=0)
    vintage_year: int
    methodology: str
    co_benefits: List[str] = []
    delivery_timeline_days: int = 30
    location: Optional[str] = None
    minimum_purchase: float = 1.0
    metadata: Dict[str, Any] = {}


class BrokerageListingOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    seller_id: uuid.UUID
    available_credits: float
    price_per_credit_usd: float
    vintage_year: int
    methodology: str
    co_benefits: List[str]
    delivery_timeline_days: int
    location: Optional[str]
    status: str
    minimum_purchase: float
    created_at: datetime


class BuyerProfileCreate(BaseModel):
    buyer_type: str
    company_name: Optional[str] = None
    preferred_methodologies: List[str] = []
    price_range_min_usd: Optional[float] = None
    price_range_max_usd: Optional[float] = None
    preferred_locations: List[str] = []
    delivery_timeline_preference_days: int = 90
    auto_match_enabled: bool = True


class BuyerProfileOut(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    buyer_type: str
    company_name: Optional[str]
    preferred_methodologies: List[str]
    price_range_min_usd: Optional[float]
    price_range_max_usd: Optional[float]
    preferred_locations: List[str]
    auto_match_enabled: bool
    created_at: datetime


class TradeMatchOut(ORMBase):
    id: uuid.UUID
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    match_score: float
    methodology_match: bool
    price_match: bool
    location_match: bool
    timeline_match: bool
    status: str
    created_at: datetime


class TransactionCreate(BaseModel):
    listing_id: uuid.UUID
    credits_amount: float = Field(..., gt=0)
    trade_type: str
    delivery_date: Optional[date] = None


class TransactionOut(ORMBase):
    id: uuid.UUID
    listing_id: uuid.UUID
    buyer_id: uuid.UUID
    seller_id: uuid.UUID
    trade_type: str
    credits_amount: float
    price_per_credit_usd: float
    total_value_usd: float
    commission_rate: float
    commission_usd: float
    status: str
    delivery_date: Optional[date]
    created_at: datetime


class EscrowOut(ORMBase):
    id: uuid.UUID
    transaction_id: uuid.UUID
    amount_usd: float
    buyer_deposited: bool
    seller_transferred: bool
    status: str
    created_at: datetime


class CommissionOut(ORMBase):
    id: uuid.UUID
    transaction_id: uuid.UUID
    amount_usd: float
    rate: float
    invoiced: bool
    created_at: datetime


# ─── Tokenization Schemas ─────────────────────────────────────────────────────

class TokenMintRequest(BaseModel):
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID
    tonnes_co2e: float = Field(..., gt=0)
    vintage_year: int
    methodology: str
    vvb_registry: str
    vvb_certificate_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class CarbonCreditTokenOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID
    tonnes_co2e: float
    vintage_year: int
    methodology: str
    vvb_registry: str
    vvb_certificate_id: Optional[str]
    radix_token_address: Optional[str]
    status: str
    is_fractional: bool
    parent_token_id: Optional[uuid.UUID]
    created_at: datetime


class TokenListingCreate(BaseModel):
    token_id: uuid.UUID
    price_per_tonne_usd: float = Field(..., gt=0)
    amount_available: float = Field(..., gt=0)


class TokenListingOut(ORMBase):
    id: uuid.UUID
    token_id: uuid.UUID
    seller_id: uuid.UUID
    price_per_tonne_usd: float
    amount_available: float
    status: str
    created_at: datetime


class TokenRetireRequest(BaseModel):
    token_id: uuid.UUID
    tonnes_retired: float = Field(..., gt=0)
    purpose: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_location: Optional[str] = None


class TokenRetirementOut(ORMBase):
    id: uuid.UUID
    token_id: uuid.UUID
    retired_by: uuid.UUID
    tonnes_retired: float
    purpose: Optional[str]
    beneficiary_name: Optional[str]
    beneficiary_location: Optional[str]
    radix_burn_tx_ref: Optional[str]
    retirement_certificate_url: Optional[str]
    created_at: datetime


# ─── Corporate Buyer Schemas ──────────────────────────────────────────────────

class CorporatePortfolioOut(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    total_credits_held: float
    total_credits_retired: float
    portfolio_value_usd: float
    esg_report_config: Dict[str, Any]
    updated_at: datetime


class PortfolioHoldingOut(ORMBase):
    id: uuid.UUID
    portfolio_id: uuid.UUID
    token_id: uuid.UUID
    tonnes_held: float
    tonnes_retired: float
    acquisition_price_usd: float
    acquired_at: datetime


class ESGReportConfig(BaseModel):
    company_name: str
    reporting_period_start: date
    reporting_period_end: date
    scope: str = "Scope 3"
    sdgs: List[str] = []


class ESGReportOut(BaseModel):
    company_name: str
    reporting_period: str
    total_offsets_tco2e: float
    total_retired_tco2e: float
    vintage_distribution: Dict[int, float]
    methodology_breakdown: Dict[str, float]
    sdg_impact_summary: Dict[str, Any]
    project_contributions: List[Dict[str, Any]]
    generated_at: datetime


# ─── Lead Intelligence ──────────────────────────────────────────────────────────

class LeadBase(BaseModel):
    registry_source: str
    external_id: str
    project_name: str
    project_developer: Optional[str] = None
    developer_contact: Optional[str] = None
    developer_email: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    location_coords: Optional[str] = None
    methodology: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = "unknown"
    crediting_period_start: Optional[date] = None
    crediting_period_end: Optional[date] = None
    last_verification_date: Optional[date] = None
    last_monitoring_period_end: Optional[date] = None
    estimated_credits_per_year: Optional[float] = None
    registry_url: Optional[str] = None
    days_in_status: Optional[int] = None
    stuck_score: float = 0.0
    priority: Optional[str] = "low"
    lead_status: Optional[str] = "new"
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    project_name: Optional[str] = None
    project_developer: Optional[str] = None
    developer_contact: Optional[str] = None
    developer_email: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    methodology: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None
    crediting_period_start: Optional[date] = None
    crediting_period_end: Optional[date] = None
    estimated_credits_per_year: Optional[float] = None
    registry_url: Optional[str] = None
    stuck_score: Optional[float] = None
    priority: Optional[str] = None
    lead_status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None


class LeadOut(LeadBase, ORMBase):
    id: uuid.UUID
    scraped_at: datetime
    updated_at: datetime
    last_scored_at: Optional[datetime] = None
    assigned_to: Optional[uuid.UUID] = None


class LeadDocumentBase(BaseModel):
    document_type: str
    source_url: str
    title: Optional[str] = None
    status: Optional[str] = "discovered"


class LeadDocumentCreate(LeadDocumentBase):
    lead_id: uuid.UUID


class LeadDocumentOut(LeadDocumentBase, ORMBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    file_hash_sha256: Optional[str] = None
    s3_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    error_message: Optional[str] = None
    fetched_at: Optional[datetime] = None
    created_at: datetime


class ProjectPreAuditOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None
    readiness_score: float
    status: str
    gap_summary: Dict[str, Any] = {}
    created_at: datetime


class LeadScoreRequest(BaseModel):
    recompute_all: bool = False


class LeadScrapeRequest(BaseModel):
    registry_source: Optional[str] = None
    country: Optional[str] = "Kenya"


class LeadBulkImportItem(BaseModel):
    external_id: str
    project_name: Optional[str] = None
    registry_url: Optional[str] = None
    status: Optional[str] = None


class LeadBulkImportRequest(BaseModel):
    registry_source: str
    items: List[LeadBulkImportItem]


class LeadBulkImportResponse(BaseModel):
    registry_source: str
    created: int
    updated: int
    queued: int
    errors: int
    leads: List[uuid.UUID]


class LeadOpportunityOut(LeadBase):
    id: uuid.UUID
    scraped_at: datetime
    updated_at: datetime
    document_count: int
    fetched_document_count: int
    converted_project_id: Optional[uuid.UUID] = None
    readiness_score: Optional[float] = None
    pre_audit_status: Optional[str] = None


class LeadStats(BaseModel):
    total_leads: int
    by_registry: Dict[str, int]
    by_priority: Dict[str, int]
    by_country: Dict[str, int]
    by_lead_status: Dict[str, int]
    avg_stuck_score: float
    high_priority_count: int
    critical_count: int


# ─── AI Application Pipeline ────────────────────────────────────────────────────

class ApplicationBase(BaseModel):
    applicant_email_hash: str
    applicant_email_encrypted: Optional[str] = None
    organization_name: Optional[str] = None
    project_title: str
    country: Optional[str] = None
    region: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None
    status: str = "intake"
    confidence_score: float = 0.0


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    organization_name: Optional[str] = None
    project_title: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None
    status: Optional[str] = None
    confidence_score: Optional[float] = None
    converted_project_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None


class ApplicationOut(ApplicationBase, ORMBase):
    id: uuid.UUID
    converted_project_id: Optional[uuid.UUID] = None
    validation_run_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ApplicationDocumentOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    source_type: str
    source_url: Optional[str] = None
    s3_key: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_hash_sha256: Optional[str] = None
    document_type: Optional[str] = None
    status: str
    extracted_text: Optional[str] = None
    extracted_entities: dict = Field(default_factory=dict)
    gap_findings: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationIntakeRequest(BaseModel):
    applicant_email: EmailStr
    organization_name: Optional[str] = None
    project_title: str
    country: Optional[str] = None
    sector: Optional[str] = None
    proposed_methodology: Optional[str] = None


# ─── Admin ────────────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    locked_users: int
    users_by_role: Dict[str, int]
    new_users_today: int
    new_users_this_week: int
    total_sessions: int
    mfa_enabled_count: int


class PermissionGrantRequest(BaseModel):
    permission: str


class PermissionRevokeRequest(BaseModel):
    permission: str


class SessionOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    device: str
    ip: str
    last_active: Optional[str] = None
    created_at: Optional[str] = None
    current: bool = False


# ─── AI-Generated Custom Methodology Schemas ───────────────────────────────────

class GeneratedMethodologyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sector: str = Field(..., min_length=1, max_length=100)
    activity_description: str = Field(..., min_length=10)
    boundaries: dict = Field(default_factory=dict)
    data_sources: list = Field(default_factory=list)


class GeneratedMethodologyCreate(GeneratedMethodologyBase):
    project_id: uuid.UUID


class GeneratedMethodologyOut(GeneratedMethodologyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    gap_analysis: Optional[dict] = None
    methodology: Optional[dict] = None
    quantification_scaffold: Optional[dict] = None
    status: str
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MethodologyTemplateOut(ORMBase):
    id: uuid.UUID
    name: str
    sector: str
    is_active: bool
    defaults_json: dict
    description: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class GeneratedMethodologyStatusUpdate(BaseModel):
    status: Literal[
        "draft", "under_review", "approved", "rejected", "revision_requested"
    ]
    rejection_reason: Optional[str] = Field(None, max_length=2000)
