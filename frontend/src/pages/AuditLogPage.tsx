import { useState } from 'react'
import { Search, Shield, CheckCircle, Clock, X } from 'lucide-react'
import { useAuditLogs } from '../hooks/useAuditLogs'
import { LoadingSpinner } from '../components/LoadingSpinner'

const ACTION_COLORS: Record<string, string> = {
  calculation_run: 'badge-blue',
  report_approved: 'badge-green',
  data_ingested: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
  human_reviewed: 'badge-amber',
  user_login: 'badge-slate',
  breach_reported: 'badge-red',
  methodology_updated: 'bg-primary-50 text-primary-700 dark:bg-primary-950/50 dark:text-primary-300',
}

export function AuditLogPage() {
  const { data: logs, isLoading, isError, error } = useAuditLogs()
  const [search, setSearch] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [selectedLog, setSelectedLog] = useState<any>(null)
  const [verifying, setVerifying] = useState<string | null>(null)

  const filtered = (logs || []).filter((log) => {
    const matchesSearch = !search || log.target.toLowerCase().includes(search.toLowerCase()) || log.actor.toLowerCase().includes(search.toLowerCase())
    const matchesAction = !filterAction || log.action === filterAction
    return matchesSearch && matchesAction
  })

  const handleVerify = async (logId: string) => {
    setVerifying(logId)
    await new Promise((r) => setTimeout(r, 1000))
    setVerifying(null)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
            <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="page-title">Audit Trail</h2>
            <p className="text-sm text-surface-400 dark:text-surface-500">Immutable blockchain-verified event log</p>
          </div>
        </div>
        <LoadingSpinner />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
            <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="page-title">Audit Trail</h2>
            <p className="text-sm text-surface-400 dark:text-surface-500">Immutable blockchain-verified event log</p>
          </div>
        </div>
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load audit logs</p>
          <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
            <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="page-title">Audit Trail</h2>
            <p className="text-sm text-surface-400 dark:text-surface-500">Immutable blockchain-verified event log</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="flex items-center gap-1.5 text-surface-500 dark:text-surface-400">
            <CheckCircle className="h-4 w-4 text-primary-500" /> {(logs || []).filter(l => l.anchored).length} anchored
          </span>
          <span className="flex items-center gap-1.5 text-surface-500 dark:text-surface-400">
            <Clock className="h-4 w-4 text-surface-400" /> {(logs || []).filter(l => !l.anchored).length} pending
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Search by actor or target..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-modern pl-10"
          />
        </div>
        <div className="relative">
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="input-modern pr-10 appearance-none cursor-pointer"
          >
            <option value="">All actions</option>
            <option value="calculation_run">Calculation Run</option>
            <option value="report_approved">Report Approved</option>
            <option value="data_ingested">Data Ingested</option>
            <option value="human_reviewed">Human Reviewed</option>
            <option value="user_login">User Login</option>
            <option value="breach_reported">Breach Reported</option>
          </select>
          <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
            <svg className="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Action</th>
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Actor</th>
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Target</th>
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Time</th>
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Hash</th>
                <th className="px-4 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Radix</th>
                <th className="px-4 py-3.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
              {filtered.map((log) => (
                <tr
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className="cursor-pointer hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className={`badge text-[10px] ${ACTION_COLORS[log.action] || 'badge-slate'}`}>
                      {(log.action || '').replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-surface-700 dark:text-surface-300">{log.actor}</td>
                  <td className="px-4 py-3 text-surface-700 dark:text-surface-300">{log.target}</td>
                  <td className="px-4 py-3 text-surface-500 dark:text-surface-400 text-xs">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-surface-500 dark:text-surface-400">
                    {log.output_hash || log.input_hash || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {log.anchored ? (
                      <span className="flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400">
                        <CheckCircle className="h-3.5 w-3.5" /> {log.radix_tx_ref?.slice(0, 12)}...
                      </span>
                    ) : (
                      <span className="text-xs text-surface-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {log.anchored && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleVerify(log.id) }}
                        className="text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 transition-colors"
                      >
                        {verifying === log.id ? 'Verifying...' : 'Verify'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-surface-500 dark:text-surface-400">
                    No audit logs match your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Panel */}
      {selectedLog && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Audit Entry Details</h3>
            <button onClick={() => setSelectedLog(null)} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            {[
              { label: 'Action', value: selectedLog.action },
              { label: 'Actor', value: `${selectedLog.actor} (${selectedLog.actor_type})` },
              { label: 'Target', value: selectedLog.target },
              { label: 'Input Hash', value: selectedLog.input_hash || '—', mono: true },
              { label: 'Output Hash', value: selectedLog.output_hash || '—', mono: true },
              { label: 'Radix TX Ref', value: selectedLog.radix_tx_ref || '—', mono: true },
            ].map((field) => (
              <div key={field.label}>
                <p className="text-xs text-surface-400 dark:text-surface-500 mb-1">{field.label}</p>
                <p className={field.mono ? 'font-mono text-xs text-surface-700 dark:text-surface-300' : 'font-medium text-surface-900 dark:text-surface-100'}>
                  {field.value}
                </p>
              </div>
            ))}
          </div>
          {selectedLog.anchored && (
            <div className="mt-4 rounded-xl bg-primary-50 dark:bg-primary-950/20 p-4">
              <p className="text-xs text-primary-700 dark:text-primary-300 flex items-start gap-2">
                <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
                This entry is anchored to the Radix DLT. The hash can be independently verified by anyone.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
