import { useQuery } from '@tanstack/react-query'
import type { ReviewQueueItem } from '../types'
import { mockReviewQueue, updateReviewQueueItem } from '../lib/mockData'

export { updateReviewQueueItem }

export function useReviewQueue(status?: string) {
  return useQuery<ReviewQueueItem[]>({
    queryKey: ['review-queue', status],
    queryFn: async () => {
      return status
        ? mockReviewQueue.filter((q) => q.status === status)
        : mockReviewQueue
    },
  })
}
