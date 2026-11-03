import { useState, useMemo } from 'react'
import {
  ShieldAlert, CheckCircle, XCircle, Clock, CheckCheck, Send, Filter,
} from 'lucide-react'
import {
  useEscalations,
  useEscalationStats,
  useAcknowledgeEscalation,
  useResolveEscalation,
} from '../../hooks/useEscalations'
import { useCommandWebSocket } from '../../hooks/useCommandWebSocket'
import StatCard from '../../components/StatCard'
import type { EscalationEvent } from '../../types'

const PRIORITY_LABELS: Record<number, string> = { 0: 'P0', 1: 'P1', 2: 'P2' }

function priorityBadge(p: number) {
  if (p === 0) return 'badge-red'
  if (p === 1) return 'badge-amber'
  return 'badge-slate'
}

function statusBadge(s: string) {
  if (s === 'open') return 'badge-red'
  if (s === 'acknowledged') return 'badge-amber'
  return 'badge-green'
}

function age(createdAt: string | null) {
  if (!createdAt) return '—'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000))
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

function formatDuration(seconds: number | null) {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

function ContextJson({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data || {})
  if (entries.length === 0) return <p className="text-xs text-surface-400">No context attached</p>
  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-4 text-xs">
          <span className="font-medium text-surface-500 dark:text-surface-400 shrink-0">{key}</span>
          <span className="text-right text-surface-700 dark:text-surface-300 break-all">
            {typeof value === 'object' ? JSON.stringify(value) : String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export function EscalationsPage() {
  const [priorityTab, setPriorityTab] = useState<'all' | 0 | 1 | 2>('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [resolving, setResolving] = useState(false)
  const [resolutionNotes, setResolutionNotes] = useState('')

  const filters = useMemo(() => ({
    ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
    ...(priorityTab !== 'all' ? { priority: priorityTab } : {}),
  }), [statusFilter, priorityTab])

  const { data, isLoading, isError, error } = useEscalations(filters)
  const { data: stats } = useEscalationStats()
  const acknowledgeMutation = useAcknowledgeEscalation()
  const resolveMutation = useResolveEscalation()
  useCommandWebSocket()

  const items = data?.items || []
  const sources = Array.from(new Set(items.map((e) => e.source))).sort()
  const filtered = sourceFilter === 'all'
    ? items
    : items.filter((e) => e.source === sourceFilter)
  const selected: EscalationEvent | null = items.find((e) => e.id === selectedId) || null

  const handleAcknowledge = (id: string) => {
    acknowledgeMutation.mutate(id)
  }

  const handleResolve = (id: string) => {
    resolveMutation.mutate(
      { id, notes: resolutionNotes },
      { onSettled: () => { setResolving(false); setResolutionNotes('') } }
    )
  }

  const avgAck = stats?.avg_time_to_ack_seconds ?? null

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Stats strip */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          title="Open P0"
          value={stats?.open_p0 ?? '—'}
          icon={<ShieldAlert className="h-5 w-5" />}
          color="rose"
        />
        <StatCard
          title="Open Escalations"
          value={stats?.by_status?.open ?? '—'}
          icon={<Clock className="h-5 w-5" />}
          color="amber"
        />
        <StatCard
          title="Resolved"
          value={stats?.by_status?.resolved ?? '—'}
          icon={<CheckCheck className="h-5 w-5" />}
          color="emerald"
        />
        <StatCard
          title="Avg Time to Ack"
          value={formatDuration(avgAck)}
          icon={<Send className="h-5 w-5" />}
          color="blue"
        />
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* List */}
        <div className={`flex flex-col ${selected ? 'w-3/5' : 'w-full'} overflow-hidden card`}>
          <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Escalations</h2>
              <span className="badge badge-blue text-[10px]">{filtered.length} items</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center rounded-lg bg-surface-100 dark:bg-surface-800 p-0.5">
                {(['all', 0, 1, 2] as const).map((p) => (
                  <button
                    key={String(p)}
                    onClick={() => setPriorityTab(p)}
                    className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                      priorityTab === p
                        ? 'bg-white dark:bg-surface-900 shadow-sm text-surface-900 dark:text-surface-100'
                        : 'text-surface-500 dark:text-surface-400 hover:text-surface-700 dark:hover:text-surface-200'
                    }`}
                  >
                    {p === 'all' ? 'All' : PRIORITY_LABELS[p]}
                  </button>
                ))}
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer w-auto"
              >
                <option value="all">All Status</option>
                <option value="open">Open</option>
                <option value="acknowledged">Acknowledged</option>
                <option value="resolved">Resolved</option>
              </select>
              <div className="relative">
                <Filter className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-surface-400" />
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="input-modern py-1.5 pl-7 pr-6 text-xs appearance-none cursor-pointer w-auto"
                >
                  <option value="all">All Sources</option>
                  {sources.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-surface-50 dark:bg-surface-900">
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Priority</th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Title</th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Source</th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-right">Severity</th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-right">Age</th>
                  <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {isError ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8">
                      <div className="card p-8 text-center">
                        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
                        <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
                      </div>
                    </td>
                  </tr>
                ) : isLoading ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-surface-400">Loading...</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-surface-400">No escalations</td></tr>
                ) : (
                  filtered.map((event) => (
                    <tr
                      key={event.id}
                      onClick={() => setSelectedId(event.id)}
                      className={`cursor-pointer transition-colors hover:bg-surface-50/50 dark:hover:bg-surface-800/30 ${
                        selected?.id === event.id ? 'bg-primary-50/50 dark:bg-primary-950/10' : ''
                      }`}
                    >
                      <td className="whitespace-nowrap px-3 py-2.5">
                        <span className={`badge text-[10px] font-bold ${priorityBadge(event.priority)}`}>
                          {PRIORITY_LABELS[event.priority] || `P${event.priority}`}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs text-surface-700 dark:text-surface-300 max-w-[240px] truncate">
                        {event.title}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-xs text-surface-500 dark:text-surface-400">
                        {event.source}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs text-surface-600 dark:text-surface-300">
                        {event.severity_score}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs text-surface-500 dark:text-surface-400">
                        {age(event.created_at)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-center">
                        <span className={`badge text-[10px] ${statusBadge(event.status)}`}>{event.status}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Detail */}
        {selected && (
          <div className="w-2/5 overflow-auto card">
            <div className="px-5 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`badge text-[10px] font-bold ${priorityBadge(selected.priority)}`}>
                    {PRIORITY_LABELS[selected.priority] || `P${selected.priority}`}
                  </span>
                  <span className={`badge text-[10px] ${statusBadge(selected.status)}`}>{selected.status}</span>
                </div>
                <button onClick={() => setSelectedId(null)} aria-label="Close" className="p-1 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                  <XCircle className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="space-y-4 p-5">
              <div>
                <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">{selected.title}</h3>
                <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">
                  Source: {selected.source} · Severity: {selected.severity_score}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Detail</p>
                <p className="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">{selected.detail}</p>
              </div>

              <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Context Package</p>
                <ContextJson data={selected.context_package} />
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Delivery Channels</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(selected.channels_sent || {}).length === 0 ? (
                    <span className="text-xs text-surface-400">None sent</span>
                  ) : (
                    Object.entries(selected.channels_sent).map(([channel, sent]) => (
                      <span
                        key={channel}
                        className={`badge text-[10px] ${sent ? 'badge-green' : 'badge-slate'}`}
                      >
                        {channel}: {sent ? 'sent' : 'not sent'}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Timeline</p>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary-500" />
                    <span className="text-surface-600 dark:text-surface-300">
                      Created — {selected.created_at ? new Date(selected.created_at).toLocaleString() : '—'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <div className={`h-1.5 w-1.5 rounded-full ${selected.acknowledged_at ? 'bg-amber-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                    <span className="text-surface-600 dark:text-surface-300">
                      Acknowledged — {selected.acknowledged_at ? new Date(selected.acknowledged_at).toLocaleString() : 'pending'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <div className={`h-1.5 w-1.5 rounded-full ${selected.resolved_at ? 'bg-green-500' : 'bg-surface-300 dark:bg-surface-600'}`} />
                    <span className="text-surface-600 dark:text-surface-300">
                      Resolved — {selected.resolved_at ? new Date(selected.resolved_at).toLocaleString() : 'pending'}
                    </span>
                  </div>
                </div>
              </div>

              {selected.resolution_notes && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Resolution Notes</p>
                  <p className="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">{selected.resolution_notes}</p>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                {selected.status === 'open' && (
                  <button
                    onClick={() => handleAcknowledge(selected.id)}
                    disabled={acknowledgeMutation.isPending}
                    className="btn-blue flex-1 px-3 py-2 text-sm"
                  >
                    <CheckCircle className="h-4 w-4" /> Acknowledge
                  </button>
                )}
                {selected.status !== 'resolved' && !resolving && (
                  <button
                    onClick={() => setResolving(true)}
                    disabled={acknowledgeMutation.isPending || resolveMutation.isPending}
                    className="btn-green flex-1 px-3 py-2 text-sm"
                  >
                    <CheckCheck className="h-4 w-4" /> Resolve
                  </button>
                )}
              </div>

              {selected.status !== 'resolved' && resolving && (
                <div className="space-y-2 rounded-xl border border-surface-200 dark:border-surface-700 p-3">
                  <textarea
                    value={resolutionNotes}
                    onChange={(e) => setResolutionNotes(e.target.value)}
                    placeholder="Resolution notes..."
                    rows={3}
                    className="input-modern text-sm"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleResolve(selected.id)}
                      disabled={resolveMutation.isPending}
                      className="btn-green flex-1 px-3 py-2 text-sm"
                    >
                      <CheckCheck className="h-4 w-4" /> Confirm Resolve
                    </button>
                    <button
                      onClick={() => { setResolving(false); setResolutionNotes('') }}
                      className="btn-ghost px-3 py-2 text-sm"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
