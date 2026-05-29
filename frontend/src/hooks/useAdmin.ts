import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { User, UserDetail, AdminStats, AdminSession } from '../types'

export function useUsers(filters?: { role?: string; is_active?: boolean; search?: string }) {
  return useQuery<User[]>({
    queryKey: ['users', filters],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters?.role) params.append('role', filters.role)
      if (filters?.is_active !== undefined) params.append('is_active', String(filters.is_active))
      if (filters?.search) params.append('search', filters.search)
      const res = await api.get(`/users/?${params.toString()}`)
      return res.data as User[]
    },
  })
}

export function useUser(id: string) {
  return useQuery<UserDetail>({
    queryKey: ['users', id],
    queryFn: async () => {
      const res = await api.get(`/users/${id}`)
      return res.data as UserDetail
    },
    enabled: !!id,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation<User, Error, { email: string; name: string; role: string; password: string; mfa_enabled?: boolean }>({
    mutationFn: async (payload) => {
      const res = await api.post('/users/', payload)
      return res.data as User
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation<User, Error, { id: string; updates: Partial<User> }>({
    mutationFn: async ({ id, updates }) => {
      const res = await api.patch(`/users/${id}`, updates)
      return res.data as User
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['users', vars.id] })
    },
  })
}

export function useDeactivateUser() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      await api.delete(`/users/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useReactivateUser() {
  const qc = useQueryClient()
  return useMutation<User, Error, string>({
    mutationFn: async (id) => {
      const res = await api.post(`/users/${id}/reactivate`)
      return res.data as User
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useUserPermissions(id: string) {
  return useQuery<string[]>({
    queryKey: ['users', id, 'permissions'],
    queryFn: async () => {
      const res = await api.get(`/users/${id}/permissions`)
      return res.data as string[]
    },
    enabled: !!id,
  })
}

export function useGrantPermission() {
  const qc = useQueryClient()
  return useMutation<string[], Error, { userId: string; permission: string }>({
    mutationFn: async ({ userId, permission }) => {
      const res = await api.post(`/users/${userId}/permissions`, { permission })
      return res.data as string[]
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['users', vars.userId, 'permissions'] })
    },
  })
}

export function useRevokePermission() {
  const qc = useQueryClient()
  return useMutation<string[], Error, { userId: string; permission: string }>({
    mutationFn: async ({ userId, permission }) => {
      const res = await api.delete(`/users/${userId}/permissions/${permission}`)
      return res.data as string[]
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['users', vars.userId, 'permissions'] })
    },
  })
}

export function useAdminStats() {
  return useQuery<AdminStats>({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      const res = await api.get('/admin/stats')
      return res.data as AdminStats
    },
  })
}

export function useAllPermissions() {
  return useQuery<string[]>({
    queryKey: ['all-permissions'],
    queryFn: async () => {
      const res = await api.get('/admin/permissions')
      return res.data.permissions as string[]
    },
  })
}

export function useUserSessions(userId: string) {
  return useQuery<AdminSession[]>({
    queryKey: ['users', userId, 'sessions'],
    queryFn: async () => {
      const res = await api.get(`/users/${userId}/sessions`)
      return res.data as AdminSession[]
    },
    enabled: !!userId,
  })
}

export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation<void, Error, { userId: string; sessionId: string }>({
    mutationFn: async ({ userId, sessionId }) => {
      await api.delete(`/users/${userId}/sessions/${sessionId}`)
    },
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['users', vars.userId, 'sessions'] })
    },
  })
}

export function useForceLogoutUser() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (userId) => {
      await api.post(`/users/${userId}/logout-all`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}

export function useCreateInvite() {
  const qc = useQueryClient()
  return useMutation<{ token: string; email: string }, Error, { email: string; name: string; role: string }>({
    mutationFn: async (payload) => {
      const res = await api.post('/auth/admin/invite', payload)
      return res.data as { token: string; email: string }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
    },
  })
}
