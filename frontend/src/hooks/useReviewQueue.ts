import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { ReviewQueueItem } from '../types'

export function useReviewQueue(status?: string) {
  return useQuery<ReviewQueueItem[]>({
    queryKey: ['review-queue', status],
    queryFn: async () => {
      const params = status ? `?status=${status}` : ''
      const res = await api.get(`/review-queue/${params}`)
      return res.data as ReviewQueueItem[]
    },
  })
}
