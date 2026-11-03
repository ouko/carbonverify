import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  EscalationEvent,
  EscalationListResponse,
  EscalationStats,
} from '../types'

export interface EscalationFilters {
  status?: string
  priority?: 0 | 1 | 2
  projectId?: string
}

export function useEscalations(filters: EscalationFilters = {}, skip = 0, limit = 50) {
  return useQuery<EscalationListResponse>({
    queryKey: ['escalations', filters, skip, limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters.status) params.append('status', filters.status)
      if (filters.priority !== undefined) params.append('priority', String(filters.priority))
      if (filters.projectId) params.append('project_id', filters.projectId)
      params.append('skip', String(skip))
      params.append('limit', String(limit))
      const res = await api.get(`/api/v1/escalations/?${params.toString()}`)
      return res.data as EscalationListResponse
    },
    refetchInterval: 30000,
  })
}

export function useEscalationStats() {
  return useQuery<EscalationStats>({
    queryKey: ['escalations', 'stats'],
    queryFn: async () => {
      const res = await api.get('/api/v1/escalations/stats')
      return res.data as EscalationStats
    },
    refetchInterval: 30000,
  })
}

export function useAcknowledgeEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/api/v1/escalations/${id}/acknowledge`)
      return res.data as EscalationEvent
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['escalations'] })
    },
  })
}

export function useResolveEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, notes }: { id: string; notes: string }) => {
      const res = await api.post(`/api/v1/escalations/${id}/resolve`, { notes })
      return res.data as EscalationEvent
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['escalations'] })
    },
  })
}
