import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  GeneratedMethodology,
  CreateGeneratedMethodologyPayload,
  UpdateMethodologyStatusPayload,
  MethodologyTemplate,
} from '../types'

export function useGeneratedMethodologies(projectId?: string) {
  return useQuery<GeneratedMethodology[]>({
    queryKey: ['generated-methodologies', projectId],
    queryFn: async () => {
      const params = projectId ? `?project_id=${projectId}` : ''
      const res = await api.get(`/methodology-generator/${params}`)
      return res.data
    },
  })
}

export function useGeneratedMethodology(id: string) {
  return useQuery<GeneratedMethodology>({
    queryKey: ['generated-methodology', id],
    queryFn: async () => {
      const res = await api.get(`/methodology-generator/${id}`)
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateGeneratedMethodology() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateGeneratedMethodologyPayload) => {
      const res = await api.post('/methodology-generator/', payload)
      return res.data as GeneratedMethodology
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['generated-methodologies'] }),
  })
}

export function useAnalyzeGap() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/methodology-generator/${id}/analyze`)
      return res.data as GeneratedMethodology
    },
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ['generated-methodology', id] }),
  })
}

export function useGenerateMethodology() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/methodology-generator/${id}/generate`)
      return res.data as GeneratedMethodology
    },
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ['generated-methodology', id] }),
  })
}

export function useUpdateMethodologyStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: UpdateMethodologyStatusPayload }) => {
      const res = await api.patch(`/methodology-generator/${id}/status`, payload)
      return res.data as GeneratedMethodology
    },
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ['generated-methodology', id] }),
  })
}

export function useMethodologyTemplates() {
  return useQuery<MethodologyTemplate[]>({
    queryKey: ['methodology-templates'],
    queryFn: async () => {
      const res = await api.get('/methodology-templates/')
      return res.data
    },
  })
}
