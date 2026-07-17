export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator' | 'developer' | 'viewer'
  mfa_enabled: boolean
  is_active: boolean
  permissions: { granted: string[]; revoked: string[] }
  created_at: string
}

export interface UserDetail extends User {
  last_login_at: string | null
  last_activity_at: string | null
  failed_login_count: number
  locked_until: string | null
  effective_permissions: string[]
}

export interface AdminStats {
  total_users: number
  active_users: number
  inactive_users: number
  locked_users: number
  users_by_role: Record<string, number>
  new_users_today: number
  new_users_this_week: number
  total_sessions: number
  mfa_enabled_count: number
}

export interface AdminSession {
  id: string
  user_id: string
  user_name: string
  user_email: string
  device: string
  ip: string
  last_active: string | null
  created_at: string | null
  current: boolean
}

export interface Project {
  id: string
  name: string
  developer_id: string
  methodology: 'TPDDTEC_v4' | 'VM0050' | 'VMR0006' | 'AMS-II.G'
  crediting_period_start: string
  crediting_period_end: string
  status: ProjectStatus
  complexity_score: number | null
  confidence_threshold: number
  created_at: string
}

export type ProjectStatus =
  | 'onboarding'
  | 'data_collection'
  | 'calculation'
  | 'review'
  | 'submitted'
  | 'verified'
  | 'monitoring'

export interface DataSource {
  id: string
  project_id: string
  source_type: 'satellite' | 'iot' | 'mobile_survey' | 'document' | 'manual_entry'
  schema_version: string
  raw_data: Record<string, unknown>
  processed_data: Record<string, unknown>
  validation_status: 'pending' | 'valid' | 'flagged' | 'rejected'
  validation_errors: string[] | null
  provenance: Record<string, unknown>
  confidence_score: number | null
  created_at: string
}

export interface DataSourceCreate {
  project_id: string
  source_type: DataSource['source_type']
  schema_version: string
  validation_status?: DataSource['validation_status']
}

export interface CalculationRun {
  id: string
  project_id: string
  monitoring_period_start: string
  monitoring_period_end: string
  fNRB_value: number | null
  emissions_reduction_tCO2e: number | null
  uncertainty_95CI: number | null
  leakage_assessment: Record<string, unknown>
  methodology_compliance_score: number | null
  confidence_score: number | null
  status: 'draft' | 'review_pending' | 'approved' | 'rejected'
  approved_by: string | null
  created_at: string
}

export interface CalculationRunCreate {
  project_id: string
  monitoring_period_start: string
  monitoring_period_end: string
  fNRB_value?: number
  emissions_reduction_tCO2e?: number
  status?: CalculationRun['status']
}

export interface Report {
  id: string
  project_id: string
  calculation_run_id: string
  template_type: 'GoldStandard_TPDDTEC' | 'Verra_VM0050'
  draft_content: Record<string, unknown>
  final_pdf: string | null
  status: 'draft' | 'human_review' | 'approved' | 'submitted' | 'vvb_approved' | 'rejected'
  vvb_feedback: Record<string, unknown> | null
  created_at: string
}

export interface ReportCreate {
  project_id: string
  calculation_run_id: string
  template_type: Report['template_type']
  draft_content?: Record<string, unknown>
  status?: Report['status']
}

export interface ReviewQueueItem {
  id: string
  item_type: 'calculation' | 'report' | 'vvb_response' | 'data_anomaly'
  item_id: string
  reason: string
  priority: number
  assigned_to: string | null
  status: 'pending' | 'in_review' | 'resolved' | 'escalated'
  resolution_notes: string | null
  created_at: string
  resolved_at: string | null
}

export interface DashboardStats {
  total_projects: number
  projects_by_status: Record<string, number>
  pending_reviews: number
  recent_calculations: number
  total_emissions_reduced: number
}

export interface ProjectCreate {
  name: string
  developer_id: string
  methodology: 'TPDDTEC_v4' | 'VM0050' | 'VMR0006' | 'AMS-II.G'
  crediting_period_start: string
  crediting_period_end: string
  status?: ProjectStatus
  complexity_score?: number | null
  confidence_threshold?: number
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
}

export type LeadRegistrySource = 'verra' | 'gold_standard' | 'cdm' | 'kenya_national' | 'manual'
export type LeadPriority = 'low' | 'medium' | 'high' | 'critical'
export type LeadWorkflowStatus = 'new' | 'contacted' | 'qualified' | 'proposal_sent' | 'converted' | 'dismissed'

export interface Lead {
  id: string
  registry_source: LeadRegistrySource
  external_id: string
  project_name: string
  project_developer: string | null
  developer_contact: string | null
  developer_email: string | null
  country: string | null
  region: string | null
  location_coords?: string | null
  methodology: string | null
  sector: string | null
  status: string
  crediting_period_start: string | null
  crediting_period_end: string | null
  last_verification_date: string | null
  last_monitoring_period_end: string | null
  estimated_credits_per_year: number | null
  registry_url: string | null
  days_in_status: number | null
  stuck_score: number
  priority: LeadPriority
  lead_status: LeadWorkflowStatus
  notes: string | null
  scraped_at: string
  updated_at: string
  last_scored_at: string | null
  assigned_to: string | null
}

export interface LeadStats {
  total_leads: number
  by_registry: Record<string, number>
  by_priority: Record<string, number>
  by_country: Record<string, number>
  by_lead_status: Record<string, number>
  avg_stuck_score: number
  high_priority_count: number
  critical_count: number
}

export interface GeneratedMethodology {
  id: string
  project_id: string
  name: string
  sector: string
  activity_description: string
  boundaries: Record<string, unknown>
  data_sources: Array<Record<string, unknown>>
  gap_analysis?: Record<string, unknown> | null
  methodology?: Record<string, unknown> | null
  quantification_scaffold?: Record<string, unknown> | null
  status: 'draft' | 'under_review' | 'approved' | 'rejected' | 'revision_requested'
  rejection_reason?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateGeneratedMethodologyPayload {
  project_id: string
  name: string
  sector: string
  activity_description: string
  boundaries: Record<string, unknown>
  data_sources: Array<Record<string, unknown>>
}

export interface UpdateMethodologyStatusPayload {
  status: GeneratedMethodology['status']
  rejection_reason?: string
}

export interface BoundariesForm {
  geographic_scope: string
  temporal_scope: string
  physical_boundary: string
  ghg_sources_included: string
}

export interface DataSourceForm {
  source_type: string
  description: string
  frequency: string
  provider_quality: string
}

export interface PageForm {
  project_id: string
  name: string
  sector: string
  activity_description: string
  boundaries: BoundariesForm
  data_sources: DataSourceForm[]
}

export interface MethodologyTemplate {
  id: string
  name: string
  sector: string
  is_active: boolean
  defaults_json: {
    boundaries: BoundariesForm
    data_sources: DataSourceForm[]
  }
  description?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export type WorkflowStepType =
  | 'http_request'
  | 'database_query'
  | 'service_call'
  | 'external_api'
  | 'notification'
  | 'dom_capture'
  | 'decision_gate'
  | 'ai_evaluation'
  | 'wait'
  | 'parallel'
  | 'subflow'

export interface RetryPolicy {
  max_retries: number
  backoff_multiplier: number
  initial_delay_ms: number
  retry_on: string[]
}

export interface CircuitBreakerConfig {
  failure_threshold: number
  recovery_timeout_ms: number
  half_open_max_calls: number
}

export interface WorkflowStep {
  id: string
  name: string
  type: WorkflowStepType
  description?: string
  enabled: boolean
  config: Record<string, unknown>
  retry_policy?: RetryPolicy
  next_on_success: string[]
  next_on_failure: string[]
  timeout_ms: number
  capture_proof: boolean
  checkpoint: boolean
  skippable: boolean
}

export interface WorkflowGraph {
  version: string
  description?: string
  entry_step: string
  retry_policy: RetryPolicy
  circuit_breaker: CircuitBreakerConfig
  steps: WorkflowStep[]
  variables: Record<string, unknown>
  human_gates_required: boolean
  sla_seconds?: number
}

export interface ValidationWorkflow {
  id: string
  name: string
  version: string
  description?: string
  active: boolean
  graph_hash: string
  workflow_graph: WorkflowGraph
  sla_seconds?: number
  human_gates_required: boolean
  created_at: string
  updated_at: string
}

export interface ValidationWorkflowCreatePayload {
  name: string
  version?: string
  description?: string
  workflow_graph: WorkflowGraph
  sla_seconds?: number
  human_gates_required?: boolean
}

export interface ValidationWorkflowUpdatePayload {
  description?: string
  active?: boolean
  workflow_graph?: WorkflowGraph
  sla_seconds?: number
  human_gates_required?: boolean
}

export interface ValidationRun {
  id: string
  workflow_id: string
  project_id?: string
  status: string
  trigger_event: string
  confidence_score?: number
  merkle_root?: string
  radix_tx_ref?: string
  started_at?: string
  completed_at?: string
  created_at: string
  error_message?: string
  remediation_count: number
  human_intervened: boolean
  awaiting_human_decision: boolean
}

export interface RunTriggerPayload {
  workflow_id: string
  project_id?: string
  trigger_event?: string
  input_data?: Record<string, unknown>
}

export interface StepExecution {
  id: string
  step_id: string
  step_index: number
  step_type: WorkflowStepType
  step_name: string
  status: string
  step_hash?: string
  duration_ms?: number
  retry_count: number
  error_message?: string
  started_at?: string
  completed_at?: string
}

export interface ValidationProof {
  id: string
  step_execution_id?: string
  proof_type: string
  proof_hash: string
  merkle_leaf_index?: number
  captured_at: string
}

export interface ValidationTransition {
  id: string
  from_state: string
  to_state: string
  actor_type: string
  reason?: string
  transition_hash: string
  previous_hash?: string
  occurred_at: string
}

export interface SyntheticActor {
  id: string
  name: string
  actor_type: string
  profile_key: string
  markers: Record<string, unknown>
  behavior_config: Record<string, unknown>
  context_data: Record<string, unknown>
  active: boolean
  usage_count: number
  created_at: string
  last_used_at?: string
}
