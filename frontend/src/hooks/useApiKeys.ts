import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  created_by: string
  last_used_at: string | null
  expires_at: string | null
  is_active: boolean
  created_at: string
}

export interface ApiKeyCreateResponse extends ApiKey {
  key: string
}

export function useApiKeys() {
  return useQuery<ApiKey[]>({
    queryKey: ['api-keys'],
    queryFn: async () => {
      const res = await api.get('/api-keys/')
      return res.data as ApiKey[]
    },
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation<ApiKeyCreateResponse, Error, { name: string; scopes: string[]; expires_in_days?: number | null }>({
    mutationFn: async (payload) => {
      const res = await api.post('/api-keys/', payload)
      return res.data as ApiKeyCreateResponse
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export function useRevokeApiKey() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await api.delete(`/api-keys/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}
