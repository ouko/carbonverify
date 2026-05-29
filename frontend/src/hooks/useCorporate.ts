import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../services/api'

export interface PortfolioProject {
  name: string
  tonnes: number
  retired: number
  vintage: number
  methodology: string
  vvb: string
}

export interface PortfolioItem {
  totalHeld: number
  totalRetired: number
  totalValue: number
  vintageDistribution: { year: number; tonnes: number }[]
  methodologyBreakdown: { name: string; value: number }[]
  projects: PortfolioProject[]
}

export interface ESGReportPayload {
  company_name: string
  reporting_period_start: string
  reporting_period_end: string
  scope?: string
  sdgs?: string[]
}

export interface ESGReportResponse {
  report_id: string
  company_name: string
  reporting_period: string
  scope: string
  total_offsets_tco2e: number
  total_retired_tco2e: number
  vintage_distribution: Record<string, number>
  methodology_breakdown: Record<string, number>
  sdg_impact_summary: Record<string, number>
  project_contributions: {
    project_id: string | null
    project_name: string | null
    tonnes_held: number
    tonnes_retired: number
    vintage: number
    methodology: string
    vvb_registry: string
  }[]
  generated_at: string
}

export interface DueDiligenceResponse {
  token_id: string
  vintage: number
  methodology: string
  vvb_registry: string
  vvb_certificate_id: string | null
  radix_token_address: string | null
  project: Record<string, unknown>
  calculation_run: Record<string, unknown>
  mrv_provenance: Record<string, unknown>
  retirement_status: string
}

// ─── Backend shape ───────────────────────────────────────────────────────────

interface BackendPortfolio {
  portfolio_id: string
  total_credits_held: number
  total_credits_retired: number
  portfolio_value_usd: number
  vintage_distribution: Record<string, number>
  methodology_breakdown: Record<string, number>
  project_contributions: {
    project_id: string | null
    project_name: string | null
    tonnes_held: number
    tonnes_retired: number
    vintage: number
    methodology: string
    vvb_registry: string
  }[]
  holdings_count: number
  retirements_count: number
}

function mapPortfolio(data: BackendPortfolio): PortfolioItem {
  return {
    totalHeld: data.total_credits_held ?? 0,
    totalRetired: data.total_credits_retired ?? 0,
    totalValue: data.portfolio_value_usd ?? 0,
    vintageDistribution: Object.entries(data.vintage_distribution ?? {}).map(
      ([year, tonnes]) => ({ year: Number(year), tonnes: Number(tonnes) })
    ),
    methodologyBreakdown: Object.entries(data.methodology_breakdown ?? {}).map(
      ([name, value]) => ({ name, value: Number(value) })
    ),
    projects: (data.project_contributions ?? []).map((p) => ({
      name: p.project_name ?? 'Unknown Project',
      tonnes: p.tonnes_held ?? 0,
      retired: p.tonnes_retired ?? 0,
      vintage: p.vintage ?? 0,
      methodology: p.methodology ?? '',
      vvb: p.vvb_registry ?? '',
    })),
  }
}

// ─── Hooks ──────────────────────────────────────────────────────────────────

export function useCorporatePortfolio() {
  return useQuery<PortfolioItem>({
    queryKey: ['corporate', 'portfolio'],
    queryFn: async () => {
      const res = await api.get<BackendPortfolio>('/corporate/portfolio')
      return mapPortfolio(res.data)
    },
  })
}

export function useGenerateESGReport() {
  return useMutation({
    mutationFn: async (payload: ESGReportPayload) => {
      const res = await api.post('/corporate/esg-report', payload)
      return res.data as ESGReportResponse
    },
  })
}

export function useDueDiligence(tokenId: string) {
  return useQuery<DueDiligenceResponse>({
    queryKey: ['corporate', 'due-diligence', tokenId],
    queryFn: async () => {
      const res = await api.get(`/corporate/due-diligence/${tokenId}`)
      return res.data as DueDiligenceResponse
    },
    enabled: !!tokenId,
  })
}
