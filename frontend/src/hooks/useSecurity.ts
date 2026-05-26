import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export interface Session {
  id: string
  device: string
  ip: string
  last_active: string
  created_at: string
  current: boolean
}

export function useSessions() {
  return useQuery<Session[]>({
    queryKey: ['sessions'],
    queryFn: async () => {
      const res = await api.get('/auth/sessions')
      return res.data as Session[]
    },
  })
}

export function useChangePassword() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ current_password, new_password }: { current_password: string; new_password: string }) => {
      const res = await api.post('/auth/change-password', { current_password, new_password })
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions'] })
    },
  })
}

export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const res = await api.delete(`/auth/sessions/${sessionId}`)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions'] })
    },
  })
}

export function useLogoutAll() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await api.post('/auth/logout-all')
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sessions'] })
    },
  })
}

export function useMFASetup() {
  return useMutation({
    mutationFn: async () => {
      const res = await api.post('/auth/mfa/setup')
      return res.data as { secret: string; qr_code: string; message: string }
    },
  })
}

export function useMFAConfirm() {
  return useMutation({
    mutationFn: async ({ secret, totp_code }: { secret: string; totp_code: string }) => {
      const res = await api.post('/auth/mfa/confirm', { secret, totp_code })
      return res.data
    },
  })
}
