import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

export function useUpdateReviewQueueItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      id,
      updates,
    }: {
      id: string
      updates: Partial<Pick<ReviewQueueItem, 'status' | 'assigned_to' | 'resolution_notes' | 'resolved_at'>>
    }) => {
      const res = await api.patch(`/review-queue/${id}`, updates)
      return res.data as ReviewQueueItem
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}

export function useDeleteReviewQueueItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/review-queue/${id}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
}
