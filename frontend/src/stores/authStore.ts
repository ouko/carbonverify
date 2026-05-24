import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../services/api'
import type { User, TokenResponse } from '../types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  setTokens: (access: string, refresh: string) => void
  setUser: (user: User | null) => void
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  initialize: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,

      setTokens: (access, refresh) => {
        set({ accessToken: access, refreshToken: refresh, isAuthenticated: true })
      },

      setUser: (user) => set({ user }),

      login: async (email, password) => {
        const res = await api.post<TokenResponse>('/auth/login', { email, password })
        const { access_token, refresh_token } = res.data
        set({ accessToken: access_token, refreshToken: refresh_token, isAuthenticated: true })
        const me = await api.get<User>('/users/me')
        set({ user: me.data, isLoading: false })
      },

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false, isLoading: false })
      },

      initialize: () => {
        const state = get()
        if (state.accessToken && !state.user) {
          api
            .get<User>('/users/me')
            .then((res) => set({ user: res.data, isLoading: false }))
            .catch(() => {
              get().logout()
            })
        } else {
          set({ isLoading: false })
        }
      },
    }),
    {
      name: 'cv-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
)
