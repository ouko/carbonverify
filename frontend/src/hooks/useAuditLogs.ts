import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export interface AuditLog {
  id: string
  action: string
  actor: string
  actor_type: 'agent' | 'user' | 'system'
  target: string
  target_type: string
  timestamp: string
  input_hash: string | null
  output_hash: string | null
  radix_tx_ref: string | null
  anchored: boolean
  mfa_used?: boolean
}

export function useAuditLogs() {
  return useQuery<AuditLog[]>({
    queryKey: ['audit-logs'],
    queryFn: async () => {
      const res = await api.get('/audit/logs')
      return res.data as AuditLog[]
    },
  })
}
