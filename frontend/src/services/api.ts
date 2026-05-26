import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../stores/authStore'

/// <reference types="vite/client" />

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
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
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config
    if (!originalRequest) return Promise.reject(error)

    const status = error.response?.status

    // Server errors — show a user-friendly message instead of blank screen
    if (status && status >= 500) {
      // Reject with a structured error so UI can show toast/alert
      return Promise.reject({
        ...error,
        isServerError: true,
        message: 'The server encountered an error. Please try again later.',
      })
    }

    if (status === 401) {
      try {
        const res = await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true })
        const { access_token } = res.data
        useAuthStore.getState().setAccessToken(access_token)
        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
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
