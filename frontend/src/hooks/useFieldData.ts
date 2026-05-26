import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

interface FieldStats {
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

interface SurveyResponse {
  id: string
  enumerator_id: string
  status: 'synced' | 'pending' | 'rejected'
  photos_count?: number
  created_at: string
}

interface SupportTicket {
  id: string
  status: 'open' | 'resolved'
  created_at: string
}

function computeStats(
  enumerators: Enumerator[],
  surveys: SurveyResponse[],
  tickets: SupportTicket[]
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
      return res.data as Enumerator[]
    },
  })

  const surveysQuery = useQuery<SurveyResponse[]>({
    queryKey: ['survey-responses'],
    queryFn: async () => {
      const res = await api.get('/whatsapp/survey-responses')
      return res.data as SurveyResponse[]
    },
  })

  const ticketsQuery = useQuery<SupportTicket[]>({
    queryKey: ['support-tickets'],
    queryFn: async () => {
      const res = await api.get('/whatsapp/support-tickets')
      return res.data as SupportTicket[]
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
    error:
      enumeratorsQuery.error || surveysQuery.error || ticketsQuery.error,
  }
}
