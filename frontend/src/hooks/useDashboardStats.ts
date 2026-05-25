import { useQuery } from '@tanstack/react-query'
import type { DashboardStats } from '../types'
import { getDashboardStats } from '../lib/mockData'

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => getDashboardStats(),
  })
}
