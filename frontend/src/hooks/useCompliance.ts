import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export interface DSR {
  id: string
  type: 'access' | 'erasure' | 'portability'
  subject_id: string
  subject_type: string
  status: 'received' | 'under_review' | 'fulfilled' | 'rejected'
  days_remaining: number
  assigned_to: string | null
  sla_deadline: string
  created_at: string
}

export interface Breach {
  id: string
  title: string
  severity: 'high' | 'medium' | 'low'
  status: 'contained' | 'notified_regulator' | 'investigating' | 'resolved'
  hours_elapsed: number
  sla_violated: boolean
  affected_subjects_count: number
}

export interface ConflictOfInterest {
  id: string
  user_id: string
  project_id: string
  relationship_type: 'financial' | 'employment' | 'personal'
  description: string
  disclosed_at: string
  approved: boolean
  reviewed_by: string | null
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
