import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { DataSource, DataSourceCreate } from '../types'

export function useDataSources() {
  return useQuery<DataSource[]>({
    queryKey: ['data-sources'],
    queryFn: async () => {
      const res = await api.get('/data-sources/')
      return res.data as DataSource[]
    },
  })
}

export function useDataSource(id: string) {
  return useQuery<DataSource>({
    queryKey: ['data-sources', id],
    queryFn: async () => {
      const res = await api.get(`/data-sources/${id}`)
      return res.data as DataSource
    },
    enabled: !!id,
  })
}

export function useCreateDataSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: DataSourceCreate) => {
      const res = await api.post('/data-sources/', payload)
      return res.data as DataSource
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['data-sources'] }),
  })
}

export function useDeleteDataSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/data-sources/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['data-sources'] }),
  })
}
