import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { Lead, LeadStats } from '../types'

export function useLeads(filters?: Record<string, string>) {
  return useQuery<Lead[]>({
    queryKey: ['leads', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          if (value) params.append(key, value)
        })
      }
      const res = await api.get(`/leads/?${params.toString()}`)
      return res.data as Lead[]
    },
  })
}

export function useLead(id: string) {
  return useQuery<Lead>({
    queryKey: ['leads', id],
    queryFn: async () => {
      const res = await api.get(`/leads/${id}`)
      return res.data as Lead
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

export interface ScraperHistoryEntry {
  scraped_at: string | null
  count: number
  created: number
  updated: number
  status: string
  data_source: string
  error_message: string | null
  mode: string
}

export function useScraperHealth() {
  return useQuery({
    queryKey: ['scraper-health'],
    queryFn: async () => {
      const res = await api.get('/leads/health/scrapers')
      return res.data as {
        verra: { status: string; message: string }
        gold_standard: { status: string; message: string }
        cdm: { status: string; message: string }
        mode: string
      }
    },
    staleTime: 30000,
  })
}

export function useScraperHistory() {
  return useQuery<Record<string, ScraperHistoryEntry | null>>({
    queryKey: ['scraper-history'],
    queryFn: async () => {
      const res = await api.get('/leads/scraper-history')
      return res.data
    },
    staleTime: 30000,
  })
}

export function useLeadsStats() {
  return useQuery<LeadStats>({
    queryKey: ['leads-stats'],
    queryFn: async () => {
      const res = await api.get('/leads/stats/dashboard')
      return res.data as LeadStats
    },
  })
}
