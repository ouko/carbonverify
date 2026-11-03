import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { AgentDecisionListResponse, HealthScore } from '../types'

export function useHealthScore() {
  return useQuery<HealthScore>({
    queryKey: ['escalations', 'health-score'],
    queryFn: async () => {
      const res = await api.get('/api/v1/escalations/health/score')
      return res.data as HealthScore
    },
    refetchInterval: 60000,
  })
}

/** Daily average agent confidence from recent audit decisions, for the trend chart. */
export function useDecisionConfidenceTrend() {
  return useQuery<Array<{ day: string; confidence: number }>>({
    queryKey: ['decision-confidence-trend'],
    queryFn: async () => {
      const res = await api.get('/api/v1/audit/decisions?action=auto_advance&limit=200&offset=0')
      const data = res.data as AgentDecisionListResponse
      const byDay = new Map<string, { sum: number; count: number }>()
      for (const d of data.decisions) {
        if (d.confidence_score === null || !d.created_at) continue
        const day = d.created_at.slice(0, 10)
        const bucket = byDay.get(day) || { sum: 0, count: 0 }
        bucket.sum += d.confidence_score
        bucket.count += 1
        byDay.set(day, bucket)
      }
      return Array.from(byDay.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([day, { sum, count }]) => ({
          day,
          confidence: Math.round((sum / count) * 1000) / 10,
        }))
    },
    refetchInterval: 60000,
  })
}
