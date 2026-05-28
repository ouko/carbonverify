import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export interface FieldStats {
  activeEnumerators: number
  surveysToday: number
  photosToday: number
  pendingSync: number
  whatsappActive: number
  whatsappMessages: number
  supportTickets: number
}

export interface Enumerator {
  id: string
  name: string
  phone: string
  surveys: number
  qualityScore: number
  rejectionRate: number
  lastSync: string
  lastSyncMinutes: number
}

interface BackendEnumerator {
  id: string
  name: string
  phone_number: string | null
  data_quality_score: number | null
  submissions_count: number | null
  rejections_count: number | null
  rejection_rate: number | null
  last_sync_at: string | null
  created_at: string | null
}

interface BackendSurvey {
  id: string
  enumerator_id: string | null
  validation_status: string
  photos_count?: number
  created_at: string | null
}

interface BackendTicket {
  id: string
  status: string
  created_at: string | null
}

function mapEnumerator(e: BackendEnumerator): Enumerator {
  const lastSync = e.last_sync_at ? new Date(e.last_sync_at) : new Date(e.created_at || 0)
  const now = new Date()
  const diffMs = now.getTime() - lastSync.getTime()
  const lastSyncMinutes = Math.max(0, Math.floor(diffMs / 60000))

  return {
    id: e.id,
    name: e.name ?? 'Unknown',
    phone: e.phone_number ?? '—',
    surveys: e.submissions_count ?? 0,
    qualityScore: Math.round((e.data_quality_score ?? 0.85) * 100),
    rejectionRate: e.rejection_rate ?? 0,
    lastSync: lastSync.toLocaleString(),
    lastSyncMinutes,
  }
}

function mapSurvey(s: BackendSurvey): { id: string; enumerator_id: string | null; status: 'synced' | 'pending' | 'rejected'; photos_count: number; created_at: string } {
  const statusMap: Record<string, 'synced' | 'pending' | 'rejected'> = {
    valid: 'synced',
    pending: 'pending',
    rejected: 'rejected',
    flagged: 'rejected',
  }
  return {
    id: s.id,
    enumerator_id: s.enumerator_id,
    status: statusMap[s.validation_status] || 'pending',
    photos_count: s.photos_count ?? 0,
    created_at: s.created_at ?? new Date().toISOString(),
  }
}

function computeStats(
  enumerators: Enumerator[],
  surveys: ReturnType<typeof mapSurvey>[],
  tickets: BackendTicket[]
): FieldStats {
  const today = new Date().toISOString().split('T')[0]
  const todaySurveys = surveys.filter((s) => s.created_at?.startsWith(today))

  return {
    activeEnumerators: enumerators.length,
    surveysToday: todaySurveys.length,
    photosToday: todaySurveys.reduce((sum, s) => sum + (s.photos_count || 0), 0),
    pendingSync: surveys.filter((s) => s.status === 'pending').length,
    whatsappActive: 0,
    whatsappMessages: 0,
    supportTickets: tickets.filter((t) => t.status === 'open').length,
  }
}

export function useFieldData() {
  const enumeratorsQuery = useQuery<Enumerator[]>({
    queryKey: ['enumerators'],
    queryFn: async () => {
      const res = await api.get('/whatsapp/enumerators')
      const data = res.data
      if (!Array.isArray(data)) return []
      return data.map((e: BackendEnumerator) => mapEnumerator(e))
    },
  })

  const surveysQuery = useQuery<ReturnType<typeof mapSurvey>[]>({
    queryKey: ['survey-responses'],
    queryFn: async () => {
      const res = await api.get('/whatsapp/survey-responses')
      const data = res.data
      if (!Array.isArray(data)) return []
      return data.map((s: BackendSurvey) => mapSurvey(s))
    },
  })

  const ticketsQuery = useQuery<BackendTicket[]>({
    queryKey: ['support-tickets'],
    queryFn: async () => {
      const res = await api.get('/whatsapp/support-tickets')
      const data = res.data
      if (!Array.isArray(data)) return []
      return data.map((t: BackendTicket) => ({
        id: t.id,
        status: t.status ?? 'open',
        created_at: t.created_at ?? new Date().toISOString(),
      }))
    },
  })

  const enumerators = enumeratorsQuery.data || []
  const surveys = surveysQuery.data || []
  const tickets = ticketsQuery.data || []

  const stats = computeStats(enumerators, surveys, tickets)

  return {
    stats,
    enumerators,
    loading: enumeratorsQuery.isLoading || surveysQuery.isLoading || ticketsQuery.isLoading,
    isError: enumeratorsQuery.isError || surveysQuery.isError || ticketsQuery.isError,
    error: enumeratorsQuery.error || surveysQuery.error || ticketsQuery.error,
  }
}
