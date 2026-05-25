export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator' | 'developer' | 'viewer'
  mfa_enabled: boolean
  created_at: string
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
  created_at: string
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
