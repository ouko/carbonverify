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
      const logs = res.data.logs || []
      return logs.map((log: any) => ({
        id: log.id,
        action: log.action_type || log.action,
        actor: log.actor_id || log.actor || 'system',
        actor_type: log.actor_type || 'system',
        target: log.target_id || log.target || '',
        target_type: log.target_type || '',
        timestamp: log.timestamp,
        input_hash: log.input_hash,
        output_hash: log.output_hash,
        radix_tx_ref: log.radix_tx_ref,
        anchored: log.radix_tx_ref != null,
      })) as AuditLog[]
    },
  })
}

export function useVerifyAuditLog() {
  return useQuery({
    queryKey: ['audit-verify'],
    queryFn: async ({ queryKey }: { queryKey: string[] }) => {
      const logId = queryKey[1]
      const res = await api.post(`/audit/logs/${logId}/verify`)
      return res.data
    },
    enabled: false,
  })
}
