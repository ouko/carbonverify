import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export interface DSR {
  id: string
  type: 'access' | 'erasure' | 'portability'
  subject: string
  status: 'received' | 'under_review' | 'fulfilled' | 'rejected'
  days_remaining: number
  assigned_to: string | null
}

export interface Breach {
  id: string
  title: string
  severity: 'high' | 'medium' | 'low'
  status: 'contained' | 'notified_regulator' | 'investigating' | 'resolved'
  hours_elapsed: number
  sla_ok: boolean
}

export interface ConflictOfInterest {
  id: string
  user: string
  project: string
  type: 'financial' | 'employment' | 'personal'
  status: 'pending_review' | 'approved' | 'rejected'
  disclosed: string
}

export function useDSRs() {
  return useQuery<DSR[]>({
    queryKey: ['compliance', 'dsr'],
    queryFn: async () => {
      const res = await api.get('/compliance/dsr')
      return res.data as DSR[]
    },
  })
}

export function useBreaches(skip = 0, limit = 50) {
  return useQuery<Breach[]>({
    queryKey: ['compliance', 'breach', skip, limit],
    queryFn: async () => {
      const res = await api.get(`/compliance/breach?skip=${skip}&limit=${limit}`)
      return res.data as Breach[]
    },
  })
}

export interface MethodologyVersion {
  id: string
  name: string
  version: string
  effective_date: string
  is_current: boolean
  change_summary: string
  approved_by: string | null
  created_at: string
}

export function useConflicts(skip = 0, limit = 50) {
  return useQuery<ConflictOfInterest[]>({
    queryKey: ['compliance', 'conflict-of-interest', skip, limit],
    queryFn: async () => {
      const res = await api.get(`/compliance/conflict-of-interest?skip=${skip}&limit=${limit}`)
      return res.data as ConflictOfInterest[]
    },
  })
}

export function useMethodologyVersions(skip = 0, limit = 50) {
  return useQuery<MethodologyVersion[]>({
    queryKey: ['compliance', 'methodology', skip, limit],
    queryFn: async () => {
      const res = await api.get(`/compliance/methodology?skip=${skip}&limit=${limit}`)
      return res.data as MethodologyVersion[]
    },
  })
}
