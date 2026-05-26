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

export interface UserSettings {
  notifyHumanReview: boolean
  notifyVVB: boolean
  notifyAnomaly: boolean
  notifyChurn: boolean
  notifyDeadline: boolean
  channelEmail: boolean
  channelInApp: boolean
  channelSMS: boolean
  channelWhatsApp: boolean
  digestMode: string
  autoAssign: boolean
  autoAdvanceThreshold: number
}

const DEFAULT_SETTINGS: UserSettings = {
  notifyHumanReview: true,
  notifyVVB: true,
  notifyAnomaly: true,
  notifyChurn: true,
  notifyDeadline: true,
  channelEmail: true,
  channelInApp: true,
  channelSMS: false,
  channelWhatsApp: false,
  digestMode: 'daily',
  autoAssign: false,
  autoAdvanceThreshold: 0.95,
}

export function useUserSettings() {
  return useQuery<UserSettings>({
    queryKey: ['user', 'settings'],
    queryFn: async () => {
      const res = await api.get('/users/me/settings')
      const settings = res.data?.settings || {}
      return { ...DEFAULT_SETTINGS, ...settings } as UserSettings
    },
  })
}

export function useUpdateUserSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (settings: UserSettings) => {
      const res = await api.put('/users/me/settings', settings)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['user', 'settings'] })
    },
  })
}
