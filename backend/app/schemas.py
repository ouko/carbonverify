import re
import uuid
from datetime import date, datetime
from enum import Enum as PyEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

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
    name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None
    mfa_enabled: bool | None = None


class UserOut(UserBase, ORMBase):
    id: uuid.UUID
    is_active: bool
    permissions: dict
    created_at: datetime


class UserDetailOut(UserOut):
    last_login_at: datetime | None = None
    last_activity_at: datetime | None = None
    failed_login_count: int = 0
    locked_until: datetime | None = None


class UserInDB(UserOut):
    hashed_password: str


class UserInviteCreate(BaseModel):
    email: EmailStr
    name: str
    role: str = "viewer"
    permissions: list[str] = []


class UserInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    token: str
    email: str
    name: str
    role: str
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None = None


class InviteAcceptRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=12)
    name: str | None = None

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
    contact_phone: str | None = None
    location: str | None = None


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
    status: str | None = "onboarding"
    complexity_score: float | None = None
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
    name: str | None = None
    status: str | None = None
    complexity_score: float | None = None
    confidence_threshold: float | None = None
    brokerage_enabled: bool | None = None
    tokenization_enabled: bool | None = None
    crediting_period_start: date | None = None
    crediting_period_end: date | None = None

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
    processing_result: dict[str, Any] | None = None
    validation_errors: list[str] | None = None
    confidence_score: float | None = None
    created_at: datetime
    processed_at: datetime | None = None


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
    raw_data: dict[str, Any] = {}
    processed_data: dict[str, Any] = {}
    validation_status: str | None = "pending"
    validation_errors: list[str] | None = None
    provenance: dict[str, Any] = {}


class DataSourceCreate(DataSourceBase):
    project_id: uuid.UUID


class DataSourceUpdate(BaseModel):
    validation_status: str | None = None
    validation_errors: list[str] | None = None
    processed_data: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    confidence_score: float | None = None


class DataSourceOut(DataSourceBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    confidence_score: float | None = None
    created_at: datetime


# ─── Calculation Runs ─────────────────────────────────────────────────────────

class CalculationRunBase(BaseModel):
    monitoring_period_start: date
    monitoring_period_end: date
    fNRB_value: float | None = None
    emissions_reduction_tCO2e: float | None = None
    uncertainty_95CI: float | None = None
    leakage_assessment: dict[str, Any] = {}
    methodology_compliance_score: float | None = None
    confidence_score: float | None = None
    status: str | None = "draft"


class CalculationRunCreate(CalculationRunBase):
    project_id: uuid.UUID


class CalculationRunUpdate(BaseModel):
    fNRB_value: float | None = None
    emissions_reduction_tCO2e: float | None = None
    uncertainty_95CI: float | None = None
    leakage_assessment: dict[str, Any] | None = None
    methodology_compliance_score: float | None = None
    confidence_score: float | None = None
    status: str | None = None
    approved_by: uuid.UUID | None = None


class CalculationRunOut(CalculationRunBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    approved_by: uuid.UUID | None = None
    created_at: datetime


# ─── Reports ──────────────────────────────────────────────────────────────────

class ReportBase(BaseModel):
    template_type: str
    draft_content: dict[str, Any] = {}
    final_pdf: str | None = None
    status: str | None = "draft"
    vvb_feedback: dict[str, Any] | None = None


class ReportCreate(ReportBase):
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID


class ReportUpdate(BaseModel):
    draft_content: dict[str, Any] | None = None
    final_pdf: str | None = None
    status: str | None = None
    vvb_feedback: dict[str, Any] | None = None


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
    status: str | None = "pending"
    resolution_notes: str | None = None


class HumanReviewQueueCreate(HumanReviewQueueBase):
    assigned_to: uuid.UUID | None = None


class HumanReviewQueueUpdate(BaseModel):
    assigned_to: uuid.UUID | None = None
    status: str | None = None
    resolution_notes: str | None = None


class HumanReviewQueueOut(HumanReviewQueueBase, ORMBase):
    id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None


# ─── IoT Webhook ──────────────────────────────────────────────────────────────

class IoTWebhookPayload(BaseModel):
    device_id: str
    timestamp: datetime
    stove_id: str | None = None
    cooking_events: int | None = None
    total_cooking_minutes: float | None = None
    temperature_avg: float | None = None
    usage_status: str | None = None
    raw_payload: dict[str, Any] = {}


class IoTWebhookResponse(BaseModel):
    received: bool
    data_source_id: uuid.UUID | None = None
    validation_status: str
    confidence_score: float | None = None
    errors: list[str] | None = None


# ─── Auth ─────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    session_id: str | None = None


class TokenPayload(BaseModel):
    sub: str | None = None
    type: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MFAVerifyRequest(BaseModel):
    temp_token: str
    totp_code: str


class MFAConfirmResponse(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    role: str | None = None
    mfa_enabled: bool = False
    backup_codes: list[str] = []


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
    scopes: list[str] = []
    expires_in_days: int | None = Field(None, ge=1, le=365)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list
    created_by: uuid.UUID
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
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
    projects_by_status: dict[str, int]
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
    data_quality_score: float | None
    submissions_count: int
    rejections_count: int
    last_sync_at: datetime | None
    created_at: datetime


class SurveyResponseOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    conversation_id: uuid.UUID
    enumerator_id: uuid.UUID | None
    household_id: str | None
    stove_id: str | None
    village_name: str | None
    responses: dict[str, Any]
    gps_latitude: float | None
    gps_longitude: float | None
    validation_status: str
    confidence_score: float | None
    submitted_via: str
    created_at: datetime


class SupportTicketOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    phone_number: str
    issue_type: str
    description: str
    status: str
    assigned_to: uuid.UUID | None
    created_at: datetime
    resolved_at: datetime | None


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
    co_benefits: list[str] = []
    delivery_timeline_days: int = 30
    location: str | None = None
    minimum_purchase: float = 1.0
    metadata: dict[str, Any] = {}


class BrokerageListingOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    seller_id: uuid.UUID
    available_credits: float
    price_per_credit_usd: float
    vintage_year: int
    methodology: str
    co_benefits: list[str]
    delivery_timeline_days: int
    location: str | None
    status: str
    minimum_purchase: float
    created_at: datetime


class BuyerProfileCreate(BaseModel):
    buyer_type: str
    company_name: str | None = None
    preferred_methodologies: list[str] = []
    price_range_min_usd: float | None = None
    price_range_max_usd: float | None = None
    preferred_locations: list[str] = []
    delivery_timeline_preference_days: int = 90
    auto_match_enabled: bool = True


class BuyerProfileOut(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    buyer_type: str
    company_name: str | None
    preferred_methodologies: list[str]
    price_range_min_usd: float | None
    price_range_max_usd: float | None
    preferred_locations: list[str]
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
    delivery_date: date | None = None


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
    delivery_date: date | None
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
    vvb_certificate_id: str | None = None
    metadata: dict[str, Any] = {}


class CarbonCreditTokenOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    calculation_run_id: uuid.UUID
    tonnes_co2e: float
    vintage_year: int
    methodology: str
    vvb_registry: str
    vvb_certificate_id: str | None
    radix_token_address: str | None
    status: str
    is_fractional: bool
    parent_token_id: uuid.UUID | None
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
    purpose: str | None = None
    beneficiary_name: str | None = None
    beneficiary_location: str | None = None


class TokenRetirementOut(ORMBase):
    id: uuid.UUID
    token_id: uuid.UUID
    retired_by: uuid.UUID
    tonnes_retired: float
    purpose: str | None
    beneficiary_name: str | None
    beneficiary_location: str | None
    radix_burn_tx_ref: str | None
    retirement_certificate_url: str | None
    created_at: datetime


# ─── Corporate Buyer Schemas ──────────────────────────────────────────────────

class CorporatePortfolioOut(ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    total_credits_held: float
    total_credits_retired: float
    portfolio_value_usd: float
    esg_report_config: dict[str, Any]
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
    sdgs: list[str] = []


class ESGReportOut(BaseModel):
    company_name: str
    reporting_period: str
    total_offsets_tco2e: float
    total_retired_tco2e: float
    vintage_distribution: dict[int, float]
    methodology_breakdown: dict[str, float]
    sdg_impact_summary: dict[str, Any]
    project_contributions: list[dict[str, Any]]
    generated_at: datetime


# ─── Lead Intelligence ──────────────────────────────────────────────────────────

class LeadBase(BaseModel):
    registry_source: str
    external_id: str
    project_name: str
    project_developer: str | None = None
    developer_contact: str | None = None
    developer_email: str | None = None
    country: str | None = None
    region: str | None = None
    location_coords: str | None = None
    methodology: str | None = None
    sector: str | None = None
    status: str | None = "unknown"
    crediting_period_start: date | None = None
    crediting_period_end: date | None = None
    last_verification_date: date | None = None
    last_monitoring_period_end: date | None = None
    estimated_credits_per_year: float | None = None
    registry_url: str | None = None
    days_in_status: int | None = None
    stuck_score: float = 0.0
    priority: str | None = "low"
    lead_status: str | None = "new"
    notes: str | None = None


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    project_name: str | None = None
    project_developer: str | None = None
    developer_contact: str | None = None
    developer_email: str | None = None
    country: str | None = None
    region: str | None = None
    methodology: str | None = None
    sector: str | None = None
    status: str | None = None
    crediting_period_start: date | None = None
    crediting_period_end: date | None = None
    estimated_credits_per_year: float | None = None
    registry_url: str | None = None
    stuck_score: float | None = None
    priority: str | None = None
    lead_status: str | None = None
    notes: str | None = None
    assigned_to: uuid.UUID | None = None


class LeadOut(LeadBase, ORMBase):
    id: uuid.UUID
    scraped_at: datetime
    updated_at: datetime
    last_scored_at: datetime | None = None
    assigned_to: uuid.UUID | None = None


class LeadDocumentBase(BaseModel):
    document_type: str
    source_url: str
    title: str | None = None
    status: str | None = "discovered"


class LeadDocumentCreate(LeadDocumentBase):
    lead_id: uuid.UUID


class LeadDocumentOut(LeadDocumentBase, ORMBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    file_hash_sha256: str | None = None
    s3_key: str | None = None
    s3_bucket: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    error_message: str | None = None
    fetched_at: datetime | None = None
    created_at: datetime


class ProjectPreAuditOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    validation_run_id: uuid.UUID | None = None
    readiness_score: float
    status: str
    gap_summary: dict[str, Any] = {}
    created_at: datetime


class LeadScoreRequest(BaseModel):
    recompute_all: bool = False


class LeadScrapeRequest(BaseModel):
    registry_source: str | None = None
    country: str | None = "Kenya"


class LeadBulkImportItem(BaseModel):
    external_id: str
    project_name: str | None = None
    registry_url: str | None = None
    status: str | None = None


class LeadBulkImportRequest(BaseModel):
    registry_source: str
    items: list[LeadBulkImportItem]


class LeadBulkImportResponse(BaseModel):
    registry_source: str
    created: int
    updated: int
    queued: int
    errors: int
    leads: list[uuid.UUID]


class LeadOpportunityOut(LeadBase):
    id: uuid.UUID
    scraped_at: datetime
    updated_at: datetime
    document_count: int
    fetched_document_count: int
    converted_project_id: uuid.UUID | None = None
    readiness_score: float | None = None
    pre_audit_status: str | None = None


class LeadStats(BaseModel):
    total_leads: int
    by_registry: dict[str, int]
    by_priority: dict[str, int]
    by_country: dict[str, int]
    by_lead_status: dict[str, int]
    avg_stuck_score: float
    high_priority_count: int
    critical_count: int


# ─── AI Application Pipeline ────────────────────────────────────────────────────

class ApplicationBase(BaseModel):
    applicant_email_hash: str
    applicant_email_encrypted: str | None = None
    organization_name: str | None = None
    project_title: str
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    proposed_methodology: str | None = None
    status: str = "intake"
    confidence_score: float = 0.0


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    organization_name: str | None = None
    project_title: str | None = None
    country: str | None = None
    region: str | None = None
    sector: str | None = None
    proposed_methodology: str | None = None
    status: str | None = None
    confidence_score: float | None = None
    converted_project_id: uuid.UUID | None = None
    validation_run_id: uuid.UUID | None = None


class ApplicationOut(ApplicationBase, ORMBase):
    id: uuid.UUID
    converted_project_id: uuid.UUID | None = None
    validation_run_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    applicant_token: str | None = None
    gap_findings: dict = Field(default_factory=dict)


class ApplicationDocumentOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    source_type: str
    source_url: str | None = None
    s3_key: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    file_hash_sha256: str | None = None
    document_type: str | None = None
    status: str
    extracted_text: str | None = None
    extracted_entities: dict = Field(default_factory=dict)
    gap_findings: dict = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationIntakeRequest(BaseModel):
    applicant_email: EmailStr
    organization_name: str | None = None
    project_title: str
    country: str | None = None
    sector: str | None = None
    proposed_methodology: str | None = None


# ─── Admin ────────────────────────────────────────────────────────────────────

class AdminStats(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    locked_users: int
    users_by_role: dict[str, int]
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
    last_active: str | None = None
    created_at: str | None = None
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
    gap_analysis: dict | None = None
    methodology: dict | None = None
    quantification_scaffold: dict | None = None
    status: str
    rejection_reason: str | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MethodologyTemplateOut(ORMBase):
    id: uuid.UUID
    name: str
    sector: str
    is_active: bool
    defaults_json: dict
    description: str | None = None
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class GeneratedMethodologyStatusUpdate(BaseModel):
    status: Literal[
        "draft", "under_review", "approved", "rejected", "revision_requested"
    ]
    rejection_reason: str | None = Field(None, max_length=2000)


# ─── Agent Decision Audit Trail ────────────────────────────────────────────────

class AgentDecisionOut(ORMBase):
    id: uuid.UUID
    decision_id: uuid.UUID
    project_id: uuid.UUID | None = None
    agent_type: str
    action: str
    confidence_score: float | None = None
    reasoning: str
    input_summary: dict | None = None
    context_package: dict | None = None
    prev_hash: str | None = None
    record_hash: str
    created_at: datetime
    actor: str
    review_queue_item_id: uuid.UUID | None = None


class AgentDecisionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    decisions: list[AgentDecisionOut]


class VerifyChainResponse(BaseModel):
    valid: bool
    checked: int
    first_broken_id: uuid.UUID | None = None
