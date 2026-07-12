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
  sessionId: string | null
  setAccessToken: (access: string, sessionId?: string) => void
  setSessionId: (sessionId: string | null) => void
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
  sessionId: null,

  setAccessToken: (access, sessionId) => {
    set({ accessToken: access, sessionId: sessionId ?? null })
  },

  setSessionId: (sessionId) => set({ sessionId }),

  setUser: (user) => set({ user }),

  login: async (email, password) => {
    const res = await api.post('/auth/login', { email, password }, { withCredentials: true })
    if (res.data.mfa_required) {
      set({ mfaRequired: true, mfaTempToken: res.data.temp_token, isLoading: false })
      return
    }
    const { access_token, session_id } = res.data
    // Set the token in the client first so /users/me can use it.
    set({ accessToken: access_token, sessionId: session_id ?? null, mfaRequired: false, mfaTempToken: null })
    try {
      const me = await api.get<User>('/users/me')
      set({ user: me.data, isAuthenticated: true, isLoading: false })
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      throw new Error('Failed to fetch user profile')
    }
  },

  verifyMFA: async (totpCode) => {
    const { mfaTempToken } = get()
    if (!mfaTempToken) throw new Error('No MFA temp token available')
    const res = await api.post('/auth/mfa/verify', { temp_token: mfaTempToken, totp_code: totpCode }, { withCredentials: true })
    const { access_token, session_id } = res.data
    set({ accessToken: access_token, sessionId: session_id ?? null, mfaRequired: false, mfaTempToken: null })
    try {
      const me = await api.get<User>('/users/me')
      set({ user: me.data, isAuthenticated: true, isLoading: false })
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      throw new Error('Failed to fetch user profile')
    }
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
        const { access_token, session_id } = res.data
        if (!access_token) throw new Error('Invalid refresh response')
        set({ accessToken: access_token, sessionId: session_id ?? null })
        return api.get<User>('/users/me')
      })
      .then((me) => {
        set({ user: me.data, isAuthenticated: true, isLoading: false })
      })
      .catch(() => {
        set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      })
  },
}))
