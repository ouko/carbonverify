import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { AgentDecision, AgentDecisionListResponse } from '../types'

/**
 * Find the agent decision that produced a human review queue item.
 *
 * The audit API has no review_queue_item_id filter, so we fetch the most
 * recent decisions and match client-side. `enabled` gates the fetch so it
 * only runs when the operator opens the audit panel for an item.
 */
export function useDecisionAudit(reviewQueueItemId: string | null, enabled: boolean) {
  return useQuery<AgentDecision | null>({
    queryKey: ['decision-audit', reviewQueueItemId],
    enabled: enabled && !!reviewQueueItemId,
    queryFn: async () => {
      const res = await api.get('/api/v1/audit/decisions?offset=0&limit=200')
      const data = res.data as AgentDecisionListResponse
      return (
        data.decisions.find((d) => d.review_queue_item_id === reviewQueueItemId) || null
      )
    },
  })
}
