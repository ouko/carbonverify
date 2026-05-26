import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { DashboardStats } from '../types'

export interface EmissionsTrendPoint {
  month: string
  value: number
}

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const res = await api.get('/dashboard/stats')
      return res.data as DashboardStats
    },
  })
}

export function useEmissionsTrend() {
  return useQuery<EmissionsTrendPoint[]>({
    queryKey: ['dashboard', 'emissions-trend'],
    queryFn: async () => {
      const res = await api.get('/dashboard/emissions-trend')
      return res.data as EmissionsTrendPoint[]
    },
  })
}
