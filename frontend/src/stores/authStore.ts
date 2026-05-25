import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../services/api'
import type { User } from '../types'

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  setAccessToken: (access: string) => void
  setUser: (user: User | null) => void
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  initialize: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: true,

      setAccessToken: (access) => {
        set({ accessToken: access, isAuthenticated: true })
      },

      setUser: (user) => set({ user }),

      login: async (email, password) => {
        const res = await api.post('/auth/login', { email, password }, { withCredentials: true })
        const { access_token } = res.data
        set({ accessToken: access_token, isAuthenticated: true })
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
        const state = get()
        if (state.accessToken && !state.user) {
          api
            .get<User>('/users/me')
            .then((res) => set({ user: res.data, isLoading: false }))
            .catch(() => {
              set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
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
      }),
    }
  )
)
