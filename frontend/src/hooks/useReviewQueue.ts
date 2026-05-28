import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { ReviewQueueItem } from '../types'

export function useReviewQueue(status?: string, skip = 0, limit = 50) {
  return useQuery<ReviewQueueItem[]>({
    queryKey: ['review-queue', status, skip, limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (status) params.append('status', status)
      params.append('skip', String(skip))
      params.append('limit', String(limit))
      const res = await api.get(`/review-queue/?${params.toString()}`)
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
