import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Monitor, X, Loader2 } from 'lucide-react'
import { api } from '../../services/api'
import LoadingSpinner from '../../components/LoadingSpinner'
import type { AdminSession } from '../../types'

function useAllSessions() {
  return useQuery<AdminSession[]>({
    queryKey: ['admin-sessions'],
    queryFn: async () => {
      const res = await api.get('/admin/sessions')
      return res.data as AdminSession[]
    },
  })
}

function useRevokeAnySession() {
  const qc = useQueryClient()
  return useMutation<void, Error, { userId: string; sessionId: string }>({
    mutationFn: async ({ userId, sessionId }) => {
      await api.delete(`/users/${userId}/sessions/${sessionId}`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-sessions'] })
    },
  })
}

export default function SessionManagementPage() {
  const { data: sessions, isLoading, isError } = useAllSessions()
  const revoke = useRevokeAnySession()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="page-title">Session Management</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
          View and revoke active user sessions across the platform
        </p>
      </div>

      {isError ? (
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load sessions</p>
        </div>
      ) : isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">User</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Device</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">IP Address</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Last Active</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {sessions?.map((session) => (
                  <tr key={session.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-semibold text-surface-900 dark:text-surface-100">{session.user_name}</p>
                        <p className="text-xs text-surface-400 dark:text-surface-500">{session.user_email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Monitor className="w-4 h-4 text-surface-400" />
                        <span className="text-surface-700 dark:text-surface-300">{session.device || 'Unknown'}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-surface-700 dark:text-surface-300 font-mono text-xs">{session.ip}</td>
                    <td className="px-6 py-4 text-surface-700 dark:text-surface-300 text-xs">
                      {session.last_active ? new Date(session.last_active).toLocaleString() : 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => revoke.mutate({ userId: session.user_id, sessionId: session.id })}
                        disabled={revoke.isPending}
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
                      >
                        {revoke.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
                {sessions?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-surface-400 dark:text-surface-500">
                      <Monitor className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      No active sessions.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
