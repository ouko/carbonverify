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
    estimated_credits_per_year: 12000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/2087',
    days_in_status: 420,
    stuck_score: 88.2,
    priority: 'critical',
    lead_status: 'new',
    notes: null,
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
    project_developer: 'LTWP Kenya',
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
    external_id: 'GS-6811',
    project_name: 'Mombasa Clean Cooking Initiative',
    project_developer: 'Hivos Impact Investments',
    developer_contact: '+254 733 456789',
    developer_email: 'kenya@hivos.org',
    country: 'Kenya',
    region: 'Mombasa',
    methodology: 'TPDDTEC_v4',
    sector: 'Household Devices',
    status: 'certified',
    crediting_period_start: '2021-01-01',
    crediting_period_end: '2030-12-31',
    last_verification_date: '2023-11-10',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 35000,
    registry_url: 'https://registry.goldstandard.org/projects/details/6811',
    days_in_status: 580,
    stuck_score: 55.3,
    priority: 'medium',
    lead_status: 'proposal_sent',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-006',
    registry_source: 'cdm',
    external_id: 'CDM-4321',
    project_name: 'Kenya Improved Biomass Cookstove',
    project_developer: 'Carbon Africa Ventures',
    developer_contact: '+254 722 555666',
    developer_email: 'projects@carbonafrica.com',
    country: 'Kenya',
    region: 'Nairobi / Central',
    methodology: 'AMS-II.G',
    sector: 'Energy Efficiency',
    status: 'registered',
    crediting_period_start: '2015-01-01',
    crediting_period_end: '2024-12-31',
    last_verification_date: '2019-06-30',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 6000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/DNV-CUK1341997645.3/view',
    days_in_status: 1825,
    stuck_score: 92.1,
    priority: 'critical',
    lead_status: 'new',
    notes: 'Crediting period ending soon — urgent conversion opportunity',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-007',
    registry_source: 'verra',
    external_id: 'VCS-VCU-2311',
    project_name: 'Nairobi Improved Cookstoves Distribution',
    project_developer: 'GreenChar Kenya',
    developer_contact: '+254 733 987654',
    developer_email: 'mrv@greenchar.org',
    country: 'Kenya',
    region: 'Nairobi',
    methodology: 'AMS-II.G',
    sector: 'Energy Efficiency',
    status: 'under_verification',
    crediting_period_start: '2023-01-01',
    crediting_period_end: '2032-12-31',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 8500,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/2311',
    days_in_status: 95,
    stuck_score: 42.8,
    priority: 'medium',
    lead_status: 'new',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-008',
    registry_source: 'gold_standard',
    external_id: 'GS-7123',
    project_name: 'Rift Valley LPG Adoption',
    project_developer: 'SafariCarbon Kenya',
    developer_contact: null,
    developer_email: 'leads@safaricarbon.com',
    country: 'Kenya',
    region: 'Nakuru',
    methodology: 'AMS-II.G',
    sector: 'Energy Efficiency',
    status: 'under_certification',
    crediting_period_start: '2022-07-01',
    crediting_period_end: '2031-06-30',
    last_verification_date: null,
    last_monitoring_period_end: null,
    estimated_credits_per_year: 15000,
    registry_url: 'https://registry.goldstandard.org/projects/details/7123',
    days_in_status: 195,
    stuck_score: 58.6,
    priority: 'medium',
    lead_status: 'contacted',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-009',
    registry_source: 'cdm',
    external_id: 'CDM-4455',
    project_name: 'East African Biogas Programme',
    project_developer: 'Hivos Biogas Programme',
    developer_contact: '+254 20 3870000',
    developer_email: 'biogas@hivos.org',
    country: 'Kenya',
    region: 'Multi-region',
    methodology: 'VM0050',
    sector: 'Agriculture/Forestry',
    status: 'registered',
    crediting_period_start: '2012-01-01',
    crediting_period_end: '2021-12-31',
    last_verification_date: '2018-03-15',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 25000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/SGS-UKL1258133759.36/view',
    days_in_status: 2190,
    stuck_score: 95.3,
    priority: 'critical',
    lead_status: 'new',
    notes: 'Legacy CDM transitioning to voluntary — massive MRV need',
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-010',
    registry_source: 'verra',
    external_id: 'VCS-VCU-1899',
    project_name: 'Western Kenya Cookstove Project',
    project_developer: 'EcoDev Ltd',
    developer_contact: '+254 722 111222',
    developer_email: 'carbon@ecodev.co.ke',
    country: 'Kenya',
    region: 'Kakamega',
    methodology: 'TPDDTEC_v4',
    sector: 'Household Devices',
    status: 'registered',
    crediting_period_start: '2020-01-01',
    crediting_period_end: '2029-12-31',
    last_verification_date: '2021-08-20',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 18000,
    registry_url: 'https://registry.verra.org/app/projectDetail/VCS/VCU/1899',
    days_in_status: 1050,
    stuck_score: 68.4,
    priority: 'high',
    lead_status: 'qualified',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-011',
    registry_source: 'gold_standard',
    external_id: 'GS-5890',
    project_name: 'Coastal Kenya Solar Lighting',
    project_developer: 'SolarNow Carbon',
    developer_contact: '+254 701 234567',
    developer_email: 'carbon@solar-now.com',
    country: 'Kenya',
    region: 'Kilifi',
    methodology: 'VMR0006',
    sector: 'Energy',
    status: 'certified',
    crediting_period_start: '2020-06-01',
    crediting_period_end: '2029-05-31',
    last_verification_date: '2022-12-01',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 8000,
    registry_url: 'https://registry.goldstandard.org/projects/details/5890',
    days_in_status: 920,
    stuck_score: 62.1,
    priority: 'high',
    lead_status: 'new',
    notes: null,
    scraped_at: '2024-06-01T08:00:00Z',
    updated_at: '2024-06-01T08:00:00Z',
    last_scored_at: '2024-06-01T08:00:00Z',
    assigned_to: null,
  },
  {
    id: 'lead-012',
    registry_source: 'cdm',
    external_id: 'CDM-3987',
    project_name: 'Kenya Off-Grid Solar',
    project_developer: 'SunFunder Carbon',
    developer_contact: null,
    developer_email: 'carbon@sunfunder.com',
    country: 'Kenya',
    region: 'Nationwide',
    methodology: 'VMR0006',
    sector: 'Energy',
    status: 'registered',
    crediting_period_start: '2014-01-01',
    crediting_period_end: '2023-12-31',
    last_verification_date: '2017-11-20',
    last_monitoring_period_end: null,
    estimated_credits_per_year: 12000,
    registry_url: 'https://cdm.unfccc.int/Projects/DB/TUV-SUD1448555963.98/view',
    days_in_status: 2555,
    stuck_score: 97.8,
    priority: 'critical',
    lead_status: 'new',
    notes: 'Expired crediting period — needs re-registration support',
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
    },
  })
}

export function useLead(id: string) {
  return useQuery<Lead>({
    queryKey: ['leads', id],
    queryFn: async () => MOCK_LEAD_MAP[id] || MOCK_LEADS[0],
    enabled: !!id,
  })
}

export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<Lead> }) => {
      const lead = MOCK_LEADS.find((l) => l.id === id)
      if (!lead) throw new Error('Lead not found')
      Object.assign(lead, updates, { updated_at: new Date().toISOString() })
      return lead
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
  })
}

export function useScrapeLeads() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { registry_source?: string; country?: string }) => {
      // For demo, simulate API call
      await new Promise((r) => setTimeout(r, 2000))
      return { created: 3, updated: 0, sources: [payload.registry_source || 'all'] }
      // When API is live:
      // const res = await api.post('/leads/scrape', payload)
      // return res.data
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
      // For demo, return mock health status
      return {
        verra: { status: 'demo', message: 'Demo mode — set LEAD_SCRAPER_MODE=live in backend .env' },
        gold_standard: { status: 'demo', message: 'Demo mode — set LEAD_SCRAPER_MODE=live in backend .env' },
        cdm: { status: 'demo', message: 'Demo mode — set LEAD_SCRAPER_MODE=live in backend .env' },
        mode: 'demo',
      }
      // When API is live:
      // const res = await api.get('/leads/health/scrapers')
      // return res.data
    },
    staleTime: 30000,
  })
}

export function useLeadsStats() {
  return useQuery<LeadStats>({
    queryKey: ['leads-stats'],
    queryFn: async () => {
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
    },
  })
}
