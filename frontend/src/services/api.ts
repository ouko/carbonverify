import axios, { AxiosError } from 'axios'
import { useAuthStore } from '../stores/authStore'

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
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

    if (error.response?.status === 401) {
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
    return Promise.reject(error)
  }
)
