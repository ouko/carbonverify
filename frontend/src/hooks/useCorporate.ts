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
  reporting_scope: string
  period_start: string
  period_end: string
}

export interface ESGReportResponse {
  report_id: string
  pdf_url: string | null
  status: string
}

export interface DueDiligenceResponse {
  token_id: string
  documents: { label: string; url: string }[]
}

export function useCorporatePortfolio() {
  return useQuery<PortfolioItem>({
    queryKey: ['corporate', 'portfolio'],
    queryFn: async () => {
      const res = await api.get('/corporate/portfolio')
      return res.data as PortfolioItem
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
