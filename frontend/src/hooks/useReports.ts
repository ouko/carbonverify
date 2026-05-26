import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { Report, ReportCreate } from '../types'

export function useReports() {
  return useQuery<Report[]>({
    queryKey: ['reports'],
    queryFn: async () => {
      const res = await api.get('/reports/')
      return res.data as Report[]
    },
  })
}

export function useReport(id: string) {
  return useQuery<Report>({
    queryKey: ['reports', id],
    queryFn: async () => {
      const res = await api.get(`/reports/${id}`)
      return res.data as Report
    },
    enabled: !!id,
  })
}

export function useCreateReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ReportCreate) => {
      const res = await api.post('/reports/', payload)
      return res.data as Report
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  })
}
