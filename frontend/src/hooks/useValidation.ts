import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export interface Escalation {
  id: string
  escalation_reason: string
  severity_score: number
  level: string
  status: 'pending' | 'acknowledged' | 'resolved' | 'timed_out'
  human_decision: string | null
  human_notes: string | null
  sla_deadline: string | null
  acknowledged_at: string | null
  resolved_at: string | null
  created_at: string
}

export function useEscalations() {
  return useQuery<Escalation[]>({
    queryKey: ['escalations'],
    queryFn: async () => {
      const res = await api.get('/validation/escalations')
      return res.data as Escalation[]
    },
  })
}

export function useAcknowledgeEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/validation/escalations/${id}/acknowledge`)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['escalations'] })
    },
  })
}

export function useResolveEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, decision, notes }: { id: string; decision: string; notes?: string }) => {
      const res = await api.post(`/validation/escalations/${id}/resolve`, { decision, notes })
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['escalations'] })
    },
  })
}
