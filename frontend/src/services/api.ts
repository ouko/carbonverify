import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../stores/authStore'

/// <reference types="vite/client" />

// In development, use a relative baseURL so requests go through the Vite proxy
// (avoids CORS issues). In production or when explicitly set, use VITE_API_URL.
const API_URL = import.meta.env.VITE_API_URL || ''

export const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  const sessionId = useAuthStore.getState().sessionId
  if (sessionId && config.headers) {
    config.headers['x-session-id'] = sessionId
  }
  return config
})

// Endpoints that should never trigger a token refresh on 401
const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout', '/auth/mfa']

let refreshPromise: Promise<any> | null = null

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config
    if (!originalRequest) return Promise.reject(error)

    const status = error.response?.status

    // Server errors — show a user-friendly message instead of blank screen
    if (status && status >= 500) {
      return Promise.reject({
        ...error,
        isServerError: true,
        message: 'The server encountered an error. Please try again later.',
      })
    }

    if (status === 401) {
      const url = originalRequest.url || ''
      const isAuthEndpoint = AUTH_ENDPOINTS.some((ep) => url.includes(ep))
      const isRetry = (originalRequest as any)._retry

      // Don't refresh on auth endpoints or if we've already retried once
      if (isAuthEndpoint || isRetry) {
        // For login/register, just propagate the 401 without redirect
        if (isAuthEndpoint && !isRetry) {
          return Promise.reject(error)
        }
        useAuthStore.getState().logout()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      (originalRequest as any)._retry = true

      // If a refresh is already in flight, wait for it instead of starting a new one
      if (refreshPromise) {
        try {
          await refreshPromise
          const token = useAuthStore.getState().accessToken
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        } catch {
          useAuthStore.getState().logout()
          window.location.href = '/login'
          return Promise.reject(error)
        }
      }

      refreshPromise = axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true })
      try {
        const res = await refreshPromise
        const { access_token, session_id } = res.data
        useAuthStore.getState().setAccessToken(access_token, session_id)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
        return Promise.reject(error)
      } finally {
        refreshPromise = null
      }
    }

    if (status === 403) {
      return Promise.reject({
        ...error,
        isForbidden: true,
        message: 'You do not have permission to perform this action.',
      })
    }

    if (status === 429) {
      return Promise.reject({
        ...error,
        isRateLimited: true,
        message: 'Too many requests. Please slow down.',
      })
    }

    return Promise.reject(error)
  }
)
