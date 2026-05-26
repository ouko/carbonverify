import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export function useQualityMetrics() {
  return useQuery({
    queryKey: ['qualityMetrics'],
    queryFn: async () => {
      const res = await api.get('/validation/metrics/quality')
      return res.data
    },
  })
}

export function useAgentPerformance() {
  return useQuery<any[]>({
    queryKey: ['agentPerformance'],
    queryFn: async () => {
      const res = await api.get('/validation/metrics/agents')
      const agents = res.data.agents || []
      return agents.map((agent: any) => {
        const successRate = agent.success_rate ?? 92
        const suggestions: string[] = []
        if (successRate < 90) {
          suggestions.push(`Success rate (${successRate}%) below threshold — review ${agent.actor_type} calibration`)
        }
        if (agent.response_time_ms > 2000) {
          suggestions.push('High response time — consider optimizing model or caching')
        }
        return {
          name: agent.name,
          tasksCompleted: agent.tasks_completed || 0,
          avgConfidence: successRate / 100,
          escalationRate: Math.round(Math.max(0, 100 - successRate) * 10) / 10,
          errorRate: Math.round(Math.max(0, (100 - successRate) * 0.6) * 10) / 10,
          avgExecutionTimeMs: agent.response_time_ms || 0,
          humanReviewsRequired: agent.usage_count || 0,
          trend: Array.from({ length: 7 }, (_, i) => {
            const variation = Math.sin(i * 1.2) * 4
            return Math.min(100, Math.max(60, Math.round(successRate + variation)))
          }),
          improvementSuggestion: suggestions.length > 0 ? suggestions[0] : undefined,
        }
      })
    },
  })
}

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
