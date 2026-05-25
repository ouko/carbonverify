import type { Project, DataSource, CalculationRun, Report, ReviewQueueItem } from '../types'

// Mutable mock data stores — mutations modify these directly
export let mockProjects: Project[] = [
  {
    id: 'proj-001',
    name: 'Kenya Clean Cookstoves — Nairobi',
    developer_id: 'dev-001',
    methodology: 'TPDDTEC_v4',
    crediting_period_start: '2023-01-01',
    crediting_period_end: '2028-12-31',
    status: 'monitoring',
    complexity_score: 7.2,
    confidence_threshold: 0.94,
    created_at: '2023-01-15T08:30:00Z',
  },
  {
    id: 'proj-002',
    name: 'Ghana Biogas Program — Accra',
    developer_id: 'dev-002',
    methodology: 'VM0050',
    crediting_period_start: '2022-06-01',
    crediting_period_end: '2027-05-31',
    status: 'verified',
    complexity_score: 8.5,
    confidence_threshold: 0.91,
    created_at: '2022-07-10T14:20:00Z',
  },
  {
    id: 'proj-003',
    name: 'Ethiopia LPG Adoption — Addis Ababa',
    developer_id: 'dev-003',
    methodology: 'AMS-II.G',
    crediting_period_start: '2024-01-01',
    crediting_period_end: '2029-12-31',
    status: 'calculation',
    complexity_score: 5.8,
    confidence_threshold: 0.87,
    created_at: '2024-02-01T09:00:00Z',
  },
  {
    id: 'proj-004',
    name: 'Nepal Improved Charcoal — Kathmandu',
    developer_id: 'dev-004',
    methodology: 'TPDDTEC_v4',
    crediting_period_start: '2023-03-01',
    crediting_period_end: '2028-02-29',
    status: 'review',
    complexity_score: 6.4,
    confidence_threshold: 0.89,
    created_at: '2023-03-20T11:45:00Z',
  },
  {
    id: 'proj-005',
    name: 'Uganda Solar Lighting — Kampala',
    developer_id: 'dev-005',
    methodology: 'VMR0006',
    crediting_period_start: '2024-06-01',
    crediting_period_end: '2029-05-31',
    status: 'data_collection',
    complexity_score: 4.2,
    confidence_threshold: 0.92,
    created_at: '2024-06-15T07:30:00Z',
  },
  {
    id: 'proj-006',
    name: 'Guatemala Stove Efficiency — Guatemala City',
    developer_id: 'dev-001',
    methodology: 'TPDDTEC_v4',
    crediting_period_start: '2022-09-01',
    crediting_period_end: '2027-08-31',
    status: 'submitted',
    complexity_score: 7.8,
    confidence_threshold: 0.90,
    created_at: '2022-10-05T16:00:00Z',
  },
]

export let mockDataSources: DataSource[] = [
  {
    id: 'ds-001', project_id: 'proj-001', source_type: 'mobile_survey',
    schema_version: 'v2.1', raw_data: {}, processed_data: {},
    validation_status: 'valid', validation_errors: null, provenance: {},
    created_at: '2024-06-01T08:00:00Z',
  },
  {
    id: 'ds-002', project_id: 'proj-001', source_type: 'satellite',
    schema_version: 'v1.5', raw_data: {}, processed_data: {},
    validation_status: 'valid', validation_errors: null, provenance: {},
    created_at: '2024-06-02T10:30:00Z',
  },
  {
    id: 'ds-003', project_id: 'proj-002', source_type: 'iot',
    schema_version: 'v3.0', raw_data: {}, processed_data: {},
    validation_status: 'flagged', validation_errors: ['Sensor offline 72h'], provenance: {},
    created_at: '2024-06-05T14:15:00Z',
  },
  {
    id: 'ds-004', project_id: 'proj-003', source_type: 'document',
    schema_version: 'v1.0', raw_data: {}, processed_data: {},
    validation_status: 'pending', validation_errors: null, provenance: {},
    created_at: '2024-06-10T09:00:00Z',
  },
  {
    id: 'ds-005', project_id: 'proj-004', source_type: 'manual_entry',
    schema_version: 'v2.0', raw_data: {}, processed_data: {},
    validation_status: 'rejected', validation_errors: ['GPS out of bounds', 'Photo quality < 50%'], provenance: {},
    created_at: '2024-06-12T16:45:00Z',
  },
]

export let mockCalculations: CalculationRun[] = [
  {
    id: 'calc-128', project_id: 'proj-001',
    monitoring_period_start: '2024-01-01', monitoring_period_end: '2024-03-31',
    fNRB_value: 0.42, emissions_reduction_tCO2e: 12450,
    uncertainty_95CI: 0.08, leakage_assessment: {},
    methodology_compliance_score: 0.94, confidence_score: 0.91,
    status: 'approved', approved_by: 'sarah.admin@carbonverify.io',
    created_at: '2024-04-10T10:00:00Z',
  },
  {
    id: 'calc-129', project_id: 'proj-002',
    monitoring_period_start: '2023-10-01', monitoring_period_end: '2023-12-31',
    fNRB_value: 0.38, emissions_reduction_tCO2e: 28700,
    uncertainty_95CI: 0.06, leakage_assessment: {},
    methodology_compliance_score: 0.96, confidence_score: 0.93,
    status: 'approved', approved_by: 'sarah.admin@carbonverify.io',
    created_at: '2024-01-15T14:30:00Z',
  },
  {
    id: 'calc-130', project_id: 'proj-003',
    monitoring_period_start: '2024-01-01', monitoring_period_end: '2024-03-31',
    fNRB_value: 0.35, emissions_reduction_tCO2e: 8200,
    uncertainty_95CI: 0.12, leakage_assessment: {},
    methodology_compliance_score: 0.78, confidence_score: 0.82,
    status: 'review_pending', approved_by: null,
    created_at: '2024-04-20T09:15:00Z',
  },
  {
    id: 'calc-131', project_id: 'proj-004',
    monitoring_period_start: '2024-01-01', monitoring_period_end: '2024-03-31',
    fNRB_value: 0.41, emissions_reduction_tCO2e: 15600,
    uncertainty_95CI: 0.09, leakage_assessment: {},
    methodology_compliance_score: 0.88, confidence_score: 0.87,
    status: 'draft', approved_by: null,
    created_at: '2024-05-01T11:00:00Z',
  },
]

export let mockReports: Report[] = [
  {
    id: 'rep-089', project_id: 'proj-001', calculation_run_id: 'calc-128',
    template_type: 'GoldStandard_TPDDTEC',
    draft_content: {},
    final_pdf: 'https://example.com/reports/rep-089.pdf',
    status: 'vvb_approved',
    vvb_feedback: null,
    created_at: '2024-05-15T10:00:00Z',
  },
  {
    id: 'rep-090', project_id: 'proj-002', calculation_run_id: 'calc-129',
    template_type: 'Verra_VM0050',
    draft_content: {},
    final_pdf: 'https://example.com/reports/rep-090.pdf',
    status: 'submitted',
    vvb_feedback: null,
    created_at: '2024-04-20T14:30:00Z',
  },
  {
    id: 'rep-091', project_id: 'proj-003', calculation_run_id: 'calc-130',
    template_type: 'GoldStandard_TPDDTEC',
    draft_content: {},
    final_pdf: null,
    status: 'human_review',
    vvb_feedback: null,
    created_at: '2024-05-25T09:00:00Z',
  },
  {
    id: 'rep-092', project_id: 'proj-004', calculation_run_id: 'calc-131',
    template_type: 'Verra_VM0050',
    draft_content: {},
    final_pdf: null,
    status: 'draft',
    vvb_feedback: null,
    created_at: '2024-06-05T11:15:00Z',
  },
]

export let mockReviewQueue: ReviewQueueItem[] = [
  {
    id: 'rq-001', item_type: 'calculation', item_id: 'calc-128',
    reason: 'Confidence below threshold (0.82) — fNRB uncertainty exceeds 15%',
    priority: 4, assigned_to: 'sarah.admin@carbonverify.io',
    status: 'in_review', resolution_notes: null,
    created_at: '2024-06-14T10:30:00Z', resolved_at: null,
  },
  {
    id: 'rq-002', item_type: 'data_anomaly', item_id: 'ds-452',
    reason: 'Photo GPS coordinates outside project boundary (2.3km deviation)',
    priority: 5, assigned_to: null,
    status: 'pending', resolution_notes: null,
    created_at: '2024-06-15T08:15:00Z', resolved_at: null,
  },
  {
    id: 'rq-003', item_type: 'report', item_id: 'rep-89',
    reason: 'VVB requested clarification on leakage assessment methodology',
    priority: 3, assigned_to: 'john.operator@carbonverify.io',
    status: 'in_review', resolution_notes: null,
    created_at: '2024-06-13T14:20:00Z', resolved_at: null,
  },
  {
    id: 'rq-004', item_type: 'vvb_response', item_id: 'vvb-34',
    reason: 'Gold Standard flagged insufficient KPT sample size (n=28, min=30)',
    priority: 4, assigned_to: null,
    status: 'pending', resolution_notes: null,
    created_at: '2024-06-15T06:00:00Z', resolved_at: null,
  },
  {
    id: 'rq-005', item_type: 'calculation', item_id: 'calc-129',
    reason: 'Cross-project anomaly detected — emissions factor 2.3x above regional average',
    priority: 2, assigned_to: 'sarah.admin@carbonverify.io',
    status: 'resolved', resolution_notes: 'Verified — improved stove technology',
    created_at: '2024-06-10T09:00:00Z', resolved_at: '2024-06-12T16:30:00Z',
  },
]

// Helpers
let idCounter = 1000
function nextId(prefix: string) {
  return `${prefix}-${(idCounter++).toString().padStart(3, '0')}`
}

export function addProject(p: Omit<Project, 'id' | 'created_at'>) {
  const project: Project = { ...p, id: nextId('proj'), created_at: new Date().toISOString() }
  mockProjects = [...mockProjects, project]
  return project
}

export function addDataSource(d: Omit<DataSource, 'id' | 'created_at'>) {
  const ds: DataSource = { ...d, id: nextId('ds'), created_at: new Date().toISOString() }
  mockDataSources = [...mockDataSources, ds]
  return ds
}

export function addCalculation(c: Omit<CalculationRun, 'id' | 'created_at'>) {
  const calc: CalculationRun = { ...c, id: nextId('calc'), created_at: new Date().toISOString() }
  mockCalculations = [...mockCalculations, calc]
  return calc
}

export function addReport(r: Omit<Report, 'id' | 'created_at'>) {
  const report: Report = { ...r, id: nextId('rep'), created_at: new Date().toISOString() }
  mockReports = [...mockReports, report]
  return report
}

export function updateReviewQueueItem(id: string, updates: Partial<ReviewQueueItem>) {
  mockReviewQueue = mockReviewQueue.map((item) =>
    item.id === id ? { ...item, ...updates } : item
  )
}

export function getProjectById(id: string) {
  return mockProjects.find((p) => p.id === id) || mockProjects[0]
}

export function getDashboardStats() {
  const byStatus: Record<string, number> = {}
  for (const p of mockProjects) {
    byStatus[p.status] = (byStatus[p.status] || 0) + 1
  }
  return {
    total_projects: mockProjects.length,
    projects_by_status: byStatus,
    pending_reviews: mockReviewQueue.filter((q) => q.status === 'pending' || q.status === 'in_review').length,
    recent_calculations: mockCalculations.filter((c) => c.status === 'approved').length,
    total_emissions_reduced: mockCalculations.reduce((sum, c) => sum + (c.emissions_reduction_tCO2e || 0), 0),
  }
}
