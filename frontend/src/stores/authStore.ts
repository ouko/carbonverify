import { create } from 'zustand'
import { api } from '../services/api'
import type { User } from '../types'

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  mfaRequired: boolean
  mfaTempToken: string | null
  setAccessToken: (access: string) => void
  setUser: (user: User | null) => void
  login: (email: string, password: string) => Promise<void>
  verifyMFA: (totpCode: string) => Promise<void>
  logout: () => Promise<void>
  initialize: () => void
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,
  mfaRequired: false,
  mfaTempToken: null,

  setAccessToken: (access) => {
    set({ accessToken: access, isAuthenticated: true })
  },

  setUser: (user) => set({ user }),

  login: async (email, password) => {
    const res = await api.post('/auth/login', { email, password }, { withCredentials: true })
    if (res.data.mfa_required) {
      set({ mfaRequired: true, mfaTempToken: res.data.temp_token, isLoading: false })
      return
    }
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true, mfaRequired: false, mfaTempToken: null })
    const me = await api.get<User>('/users/me')
    set({ user: me.data, isLoading: false })
  },

  verifyMFA: async (totpCode) => {
    const { mfaTempToken } = get()
    if (!mfaTempToken) throw new Error('No MFA temp token available')
    const res = await api.post('/auth/mfa/verify', { temp_token: mfaTempToken, totp_code: totpCode }, { withCredentials: true })
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true, mfaRequired: false, mfaTempToken: null })
    const me = await api.get<User>('/users/me')
    set({ user: me.data, isLoading: false })
  },

  logout: async () => {
    try {
      await api.post('/auth/logout', {}, { withCredentials: true })
    } catch {
      // Ignore logout errors
    }
    set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
  },

  initialize: () => {
    // Attempt silent refresh using the httpOnly refresh-token cookie.
    // Access tokens are memory-only (never persisted to localStorage)
    // to prevent XSS exfiltration.
    api
      .post('/auth/refresh', {}, { withCredentials: true })
      .then((res) => {
        const { access_token } = res.data
        set({ accessToken: access_token, isAuthenticated: true })
        return api.get<User>('/users/me')
      })
      .then((me) => {
        set({ user: me.data, isLoading: false })
      })
      .catch(() => {
        set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      })
  },
}))
