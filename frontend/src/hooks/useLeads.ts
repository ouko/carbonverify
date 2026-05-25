import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { Lead, LeadStats } from '../types'

const MOCK_LEADS: Lead[] = [
  {
    id: 'lead-001',
    registry_source: 'verra',
    external_id: 'VCS-VCU-1952',
    project_name: 'Kenya Household Energy Project — Embu',
    project_developer: 'EcoAct Kenya Ltd',
    developer_contact: '+254 722 123456',
    developer_email: 'projects@ecoact.co.ke',
    country: 'Kenya',
    region: 'Embu County',
    methodology: 'VMR0006',
    sector: 'Energy',
    status: 'under_verification',
    crediting_period_start: '2022-01-01',
    crediting_period_end: '2031-12-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 45000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/1952',
    days_in_status: 245,
    stuck_score: 72.5,
    priority: 'high',
    lead_status: 'new',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-002',
    registry_source: 'verra',
    external_id: 'VCS-VCU-2087',
    project_name: 'Borehole Rehabilitation Programme — Kwale',
    project_developer: 'CarbonLink Africa',
    developer_contact: null,
    developer_email: 'info@carbonlink.africa',
    country: 'Kenya',
    region: 'Kwale County',
    methodology: 'VM0050',
    sector: 'Energy Efficiency',
    status: 'under_validation',
    crediting_period_start: '2021-06-01',
    crediting_period_end: '2028-05-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 120000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/2087',
    days_in_status: 410,
    stuck_score: 88.2,
    priority: 'critical',
    lead_status: 'qualified',
    notes: 'POA structure, multiple VPAs — high upsell potential',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-003',
    registry_source: 'verra',
    external_id: 'VCS-VCU-1543',
    project_name: 'Lake Turkana Wind Power',
    project_developer: 'LTWP Carbon Ltd',
    developer_contact: '+254 20 1234567',
    developer_email: 'carbon@ltwp.co.ke',
    country: 'Kenya',
    region: 'Marsabit County',
    methodology: 'VM0055',
    sector: 'Energy',
    status: 'registered',
    crediting_period_start: '2019-01-01',
    crediting_period_end: '2038-12-31',
    last_verification_date: '2022-03-15',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 320000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/1543',
    days_in_status: 890,
    stuck_score: 65.8,
    priority: 'high',
    lead_status: 'contacted',
    notes: 'Developer responsive, needs MRV platform demo',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-004',
    registry_source: 'gold_standard',
    external_id: 'GS-7542',
    project_name: 'Kisumu Biogas Program',
    project_developer: 'Biogas Solutions East Africa',
    developer_contact: '+254 712 345678',
    developer_email: 'carbon@biogas-ea.org',
    country: 'Kenya',
    region: 'Kisumu',
    methodology: 'VM0050',
    sector: 'Clean Cooking',
    status: 'under_certification',
    crediting_period_start: '2023-03-01',
    crediting_period_end: '2033-02-28',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 22000,
    registry_url: 'https://registry.goldstandard.org/projects/details/7542',
    days_in_status: 310,
    stuck_score: 78.4,
    priority: 'high',
    lead_status: 'qualified',
    notes: 'POA coordinator manages 3 VPAs — upsell opportunity',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-005',
    registry_source: 'gold_standard',
    external_id: 'GS-8912',
    project_name: 'Nakuru Reforestation Initiative',
    project_developer: 'Green Belt Movement',
    developer_contact: '+254 733 987654',
    developer_email: 'carbon@greenbelt.or.ke',
    country: 'Kenya',
    region: 'Nakuru',
    methodology: 'AR-ACM0003',
    sector: 'Forestry',
    status: 'under_validation',
    crediting_period_start: '2022-08-01',
    crediting_period_end: '2042-07-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 8500,
    registry_url: 'https://registry.goldstandard.org/projects/details/8912',
    days_in_status: 520,
    stuck_score: 91.0,
    priority: 'critical',
    lead_status: 'new',
    notes: 'Large NGO, budget cycle aligns Q3',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-006',
    registry_source: 'cdm',
    external_id: 'CDM-8324',
    project_name: 'Kakamega Efficient Cookstoves',
    project_developer: 'EcoChar Africa',
    developer_contact: '+254 701 112233',
    developer_email: 'projects@ecochar.co.ke',
    country: 'Kenya',
    region: 'Kakamega',
    methodology: 'AMS-II.G',
    sector: 'Clean Cooking',
    status: 'request_for_issuance',
    crediting_period_start: '2018-01-01',
    crediting_period_end: '2025-12-31',
    last_verification_date: '2023-11-20',
    last_monitoring_period_end: '2023-06-30',
    estimated_credits_per_year: 18000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/DNV-CUK1321651524.11/view',
    days_in_status: 45,
    stuck_score: 42.0,
    priority: 'medium',
    lead_status: 'new',
    notes: 'Transitioning to voluntary market — timing sensitive',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-007',
    registry_source: 'cdm',
    external_id: 'CDM-9102',
    project_name: 'Mombasa Landfill Gas Recovery',
    project_developer: 'Waste Energy Kenya',
    developer_contact: '+254 722 445566',
    developer_email: 'info@wasteenergy.co.ke',
    country: 'Kenya',
    region: 'Mombasa',
    methodology: 'ACM0001',
    sector: 'Waste',
    status: 'registered',
    crediting_period_start: '2015-01-01',
    crediting_period_end: '2025-12-31',
    last_verification_date: '2021-09-10',
    last_monitoring_period_end: '2021-03-31',
    estimated_credits_per_year: 55000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/TUEV-SUD1310527229.48/view',
    days_in_status: 1100,
    stuck_score: 95.5,
    priority: 'critical',
    lead_status: 'proposal_sent',
    notes: 'Crediting period ends 2025-12 — urgent renewal conversation',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-008',
    registry_source: 'verra',
    external_id: 'VCS-VCU-3124',
    project_name: 'Mau Forest Restoration',
    project_developer: 'Kenya Forest Service',
    developer_contact: '+254 20 2345678',
    developer_email: 'carbon@kenyaforestservice.org',
    country: 'Kenya',
    region: 'Mau Complex',
    methodology: 'AR-ACM0003',
    sector: 'Forestry',
    status: 'under_validation',
    crediting_period_start: '2023-01-01',
    crediting_period_end: '2053-12-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 45000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/3124',
    days_in_status: 180,
    stuck_score: 58.0,
    priority: 'medium',
    lead_status: 'new',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-009',
    registry_source: 'gold_standard',
    external_id: 'GS-4451',
    project_name: 'Mombasa Solar Mini-Grid',
    project_developer: 'Rural Electrification Authority',
    developer_contact: '+254 20 3456789',
    developer_email: 'carbon@rea.co.ke',
    country: 'Kenya',
    region: 'Mombasa',
    methodology: 'VMR0006',
    sector: 'Energy',
    status: 'registered',
    crediting_period_start: '2021-01-01',
    crediting_period_end: '2031-12-31',
    last_verification_date: '2023-05-15',
    last_monitoring_period_end: '2022-12-31',
    estimated_credits_per_year: 12000,
    registry_url: 'https://registry.goldstandard.org/projects/details/4451',
    days_in_status: 620,
    stuck_score: 68.5,
    priority: 'high',
    lead_status: 'contacted',
    notes: 'Government entity, slow procurement cycle',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-010',
    registry_source: 'cdm',
    external_id: 'CDM-5532',
    project_name: 'Kiambu Dairy Biogas',
    project_developer: 'Smallholder Dairy Cooperative',
    developer_contact: '+254 733 223344',
    developer_email: null,
    country: 'Kenya',
    region: 'Kiambu',
    methodology: 'AMS-I.D',
    sector: 'Agriculture',
    status: 'request_for_issuance',
    crediting_period_start: '2019-06-01',
    crediting_period_end: '2029-05-31',
    last_verification_date: '2024-01-10',
    last_monitoring_period_end: '2023-06-30',
    estimated_credits_per_year: 8000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/SGS-UK1321649876.22/view',
    days_in_status: 120,
    stuck_score: 55.0,
    priority: 'medium',
    lead_status: 'new',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-011',
    registry_source: 'verra',
    external_id: 'VCS-VCU-4455',
    project_name: 'Nairobi BRT Emissions Reduction',
    project_developer: 'Transport Carbon Africa',
    developer_contact: '+254 722 998877',
    developer_email: 'carbon@transportafrica.org',
    country: 'Kenya',
    region: 'Nairobi',
    methodology: 'VM0055',
    sector: 'Transport',
    status: 'under_verification',
    crediting_period_start: '2024-01-01',
    crediting_period_end: '2034-12-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 95000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/4455',
    days_in_status: 90,
    stuck_score: 48.0,
    priority: 'low',
    lead_status: 'new',
    notes: 'New project, early stage engagement',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-012',
    registry_source: 'gold_standard',
    external_id: 'GS-2288',
    project_name: 'Meru Wind Farm Phase II',
    project_developer: 'Meru Wind Power Ltd',
    developer_contact: '+254 722 556677',
    developer_email: 'info@meruwind.co.ke',
    country: 'Kenya',
    region: 'Meru',
    methodology: 'VMR0006',
    sector: 'Energy',
    status: 'under_certification',
    crediting_period_start: '2022-01-01',
    crediting_period_end: '2042-12-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 185000,
    registry_url: 'https://registry.goldstandard.org/projects/details/2288',
    days_in_status: 275,
    stuck_score: 75.0,
    priority: 'high',
    lead_status: 'qualified',
    notes: 'Large-scale, developer previously used competitor platform',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
]

const MOCK_LEAD_MAP: Record<string, Lead> = Object.fromEntries(MOCK_LEADS.map((l) => [l.id, l]))

export function useLeads(filters?: Record<string, string>) {
  return useQuery<Lead[]>({
    queryKey: ['leads', filters],
    queryFn: async () => {
      try {
        const params = new URLSearchParams()
        if (filters) {
          Object.entries(filters).forEach(([key, value]) => {
            if (value) params.append(key, value)
          })
        }
        const res = await api.get(`/leads/?${params.toString()}`)
        return res.data as Lead[]
      } catch {
        // Fallback to mock data if API is unreachable
        let data = MOCK_LEADS
        if (filters) {
          if (filters.registry_source) data = data.filter((l) => l.registry_source === filters.registry_source)
          if (filters.country) data = data.filter((l) => l.country === filters.country)
          if (filters.priority) data = data.filter((l) => l.priority === filters.priority)
          if (filters.lead_status) data = data.filter((l) => l.lead_status === filters.lead_status)
          if (filters.search) {
            const q = filters.search.toLowerCase()
            data = data.filter((l) => l.project_name.toLowerCase().includes(q) || (l.project_developer?.toLowerCase().includes(q) ?? false))
          }
        }
        return data.sort((a, b) => b.stuck_score - a.stuck_score)
      }
    },
  })
}

export function useLead(id: string) {
  return useQuery<Lead>({
    queryKey: ['leads', id],
    queryFn: async () => {
      try {
        const res = await api.get(`/leads/${id}`)
        return res.data as Lead
      } catch {
        return MOCK_LEAD_MAP[id] || MOCK_LEADS[0]
      }
    },
    enabled: !!id,
  })
}

export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<Lead> }) => {
      const res = await api.patch(`/leads/${id}`, updates)
      return res.data as Lead
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
  })
}

export function useDeleteLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/leads/${id}`)
      return id
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
  })
}

export interface ScrapeResult {
  created: number
  updated: number
  sources: string[]
  per_source: {
    source: string
    status: 'live' | 'demo' | 'error'
    count: number
    created: number
    updated: number
    error: string | null
    data_source: string
  }[]
}

export function useScrapeLeads() {
  const qc = useQueryClient()
  return useMutation<ScrapeResult, Error, { registry_source?: string; country?: string }>({
    mutationFn: async (payload) => {
      const res = await api.post('/leads/scrape', payload)
      return res.data as ScrapeResult
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['leads'] })
      qc.invalidateQueries({ queryKey: ['leads-stats'] })
    },
  })
}

export function useScraperHealth() {
  return useQuery({
    queryKey: ['scraper-health'],
    queryFn: async () => {
      try {
        const res = await api.get('/leads/health/scrapers')
        return res.data as {
          verra: { status: string; message: string }
          gold_standard: { status: string; message: string }
          cdm: { status: string; message: string }
          mode: string
        }
      } catch {
        return {
          verra: { status: 'demo', message: 'Backend unreachable — using mock data' },
          gold_standard: { status: 'demo', message: 'Backend unreachable — using mock data' },
          cdm: { status: 'demo', message: 'Backend unreachable — using mock data' },
          mode: 'demo',
        }
      }
    },
    staleTime: 30000,
  })
}

export function useLeadsStats() {
  return useQuery<LeadStats>({
    queryKey: ['leads-stats'],
    queryFn: async () => {
      try {
        const res = await api.get('/leads/stats/dashboard')
        return res.data as LeadStats
      } catch {
        const total = MOCK_LEADS.length
        const by_registry: Record<string, number> = {}
        const by_priority: Record<string, number> = {}
        const by_country: Record<string, number> = {}
        const by_lead_status: Record<string, number> = {}
        let sumScore = 0
        let high = 0
        let critical = 0
        for (const l of MOCK_LEADS) {
          by_registry[l.registry_source] = (by_registry[l.registry_source] || 0) + 1
          by_priority[l.priority] = (by_priority[l.priority] || 0) + 1
          by_country[l.country || 'Unknown'] = (by_country[l.country || 'Unknown'] || 0) + 1
          by_lead_status[l.lead_status] = (by_lead_status[l.lead_status] || 0) + 1
          sumScore += l.stuck_score
          if (l.priority === 'high' || l.priority === 'critical') high++
          if (l.priority === 'critical') critical++
        }
        return {
          total_leads: total,
          by_registry,
          by_priority,
          by_country,
          by_lead_status,
          avg_stuck_score: Math.round((sumScore / total) * 10) / 10,
          high_priority_count: high,
          critical_count: critical,
        }
      }
    },
  })
}
