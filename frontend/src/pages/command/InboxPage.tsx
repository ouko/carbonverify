import { useState, useEffect } from 'react'
import {
  CheckCircle, XCircle, HelpCircle, ArrowUpCircle, UserCheck,
  Clock, AlertTriangle, TrendingUp, Filter,
} from 'lucide-react'
import { useReviewQueue, useUpdateReviewQueueItem } from '../../hooks/useReviewQueue'
import { useCommandWebSocket } from '../../hooks/useCommandWebSocket'

export function InboxPage() {
  const { data: items, isLoading, isError, error } = useReviewQueue()
  const updateMutation = useUpdateReviewQueueItem()
  interface LocalItem {
    id: string
    priority: number
    itemType: string
    reason: string
    subject: string
    assignedTo: string | null
    status: string
    createdAt: string
    resolvedAt: string | null
    projectName: string
    projectId: string
    financialImpact: number
    confidence: number
    hoursInQueue: number
    suggestedAction: string
  }

  const [localItems, setLocalItems] = useState<LocalItem[]>([])
  const [selectedItem, setSelectedItem] = useState<LocalItem | null>(null)
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [actingId, setActingId] = useState<string | null>(null)
  useCommandWebSocket()

  useEffect(() => {
    if (items) {
      setLocalItems(
        items.map((item) => ({
          id: item.id,
          priority: item.priority,
          itemType: item.item_type,
          reason: item.reason,
          subject: item.reason.length > 60 ? item.reason.slice(0, 60) + '…' : item.reason,
          assignedTo: item.assigned_to,
          status: item.status,
          createdAt: item.created_at,
          resolvedAt: item.resolved_at,
          // Fallbacks for fields the UI expects but the API doesn't provide
          projectName: item.item_id,
          projectId: item.item_id,
          financialImpact: 0,
          confidence: 1,
          hoursInQueue: Math.max(0, Math.round((Date.now() - new Date(item.created_at).getTime()) / (1000 * 60 * 60) * 10) / 10),
          suggestedAction: 'Review',
        }))
      )
    }
  }, [items])

  const filtered = localItems.filter((item: any) => {
    if (filterType !== 'all' && item.itemType !== filterType) return false
    if (filterStatus !== 'all' && item.status !== filterStatus) return false
    return true
  })

  const getPriorityColor = (p: number) => {
    if (p === 5) return 'badge-red'
    if (p === 4) return 'bg-orange-50 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300'
    if (p === 3) return 'badge-amber'
    return 'badge-green'
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'calculation': return <TrendingUp className="h-4 w-4" />
      case 'report': return <AlertTriangle className="h-4 w-4" />
      case 'data_anomaly': return <AlertTriangle className="h-4 w-4 text-red-500" />
      case 'agent_review': return <HelpCircle className="h-4 w-4" />
      case 'vvb_response': return <ArrowUpCircle className="h-4 w-4" />
      default: return <HelpCircle className="h-4 w-4" />
    }
  }

  const mutateItem = (id: string, updates: any) => {
    setLocalItems((prev) => prev.map((it) => it.id === id ? { ...it, ...updates } : it))
    if (selectedItem?.id === id) {
      setSelectedItem((prev: any) => ({ ...prev, ...updates }))
    }
  }

  const handleApprove = (id: string) => {
    setActingId(id)
    mutateItem(id, { status: 'resolved', resolvedAt: new Date().toISOString() })
    updateMutation.mutate(
      { id, updates: { status: 'resolved', resolved_at: new Date().toISOString() } },
      { onSettled: () => setActingId(null) }
    )
  }

  const handleRequestInfo = (id: string) => {
    setActingId(id)
    mutateItem(id, { status: 'pending' })
    updateMutation.mutate(
      { id, updates: { status: 'pending', resolution_notes: 'Information requested' } },
      { onSettled: () => setActingId(null) }
    )
  }

  const handleEscalate = (id: string) => {
    setActingId(id)
    mutateItem(id, { status: 'escalated', priority: Math.min(5, (localItems.find((i) => i.id === id)?.priority || 1) + 1) })
    updateMutation.mutate(
      { id, updates: { status: 'escalated' } },
      { onSettled: () => setActingId(null) }
    )
  }

  const handleAssign = (id: string) => {
    setActingId(id)
    mutateItem(id, { assignedTo: 'Current User', status: 'in_review' })
    updateMutation.mutate(
      { id, updates: { assigned_to: 'Current User', status: 'in_review' } },
      { onSettled: () => setActingId(null) }
    )
  }

  return (
    <div className="flex h-full gap-4">
      {/* Queue Table */}
      <div className={`flex flex-col ${selectedItem ? 'w-3/5' : 'w-full'} overflow-hidden card`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Priority Queue</h2>
            <span className="badge badge-blue text-[10px]">
              {filtered.length} items
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Filter className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-surface-400" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="input-modern py-1.5 pl-7 pr-6 text-xs appearance-none cursor-pointer"
              >
                <option value="all">All Types</option>
                <option value="calculation">Calculation</option>
                <option value="report">Report</option>
                <option value="data_anomaly">Data Anomaly</option>
                <option value="agent_review">Agent Review</option>
                <option value="vvb_response">VVB Response</option>
              </select>
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="in_review">In Review</option>
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-surface-50 dark:bg-surface-900">
              <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Priority</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Project</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Type</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400">Reason</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-right">Conf</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-right">Queue</th>
                <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
              {isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8">
                    <div className="card p-8 text-center">
                      <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
                      <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
                    </div>
                  </td>
                </tr>
              ) : isLoading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-surface-400">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-surface-400">No items in queue</td></tr>
              ) : (
                filtered.map((item: any) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className={`cursor-pointer transition-colors hover:bg-surface-50/50 dark:hover:bg-surface-800/30 ${
                      selectedItem?.id === item.id ? 'bg-primary-50/50 dark:bg-primary-950/10' : ''
                    }`}
                  >
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <span className={`badge text-[10px] font-bold ${getPriorityColor(item.priority)}`}>
                        P{item.priority}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="text-sm font-medium text-surface-900 dark:text-surface-100">{item.projectName}</div>
                      <div className="text-xs text-surface-400 dark:text-surface-500">${item.financialImpact.toLocaleString()}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 text-xs text-surface-600 dark:text-surface-300">
                        {getTypeIcon(item.itemType)}
                        <span className="capitalize">{(item.itemType || '').replace('_', ' ')}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-surface-600 dark:text-surface-300 max-w-[200px] truncate">
                      {item.subject}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs">
                      <span className={item.confidence < 0.85 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-surface-600 dark:text-surface-300'}>
                        {Math.round(item.confidence * 100)}%
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs text-surface-500 dark:text-surface-400">
                      <div className="flex items-center justify-end gap-1">
                        <Clock className="h-3 w-3" />
                        {item.hoursInQueue}h
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <div className="flex justify-center gap-0.5">
                        <button
                          title="Approve"
                          disabled={actingId === item.id}
                          onClick={(e) => { e.stopPropagation(); handleApprove(item.id) }}
                          className="p-1.5 rounded-lg text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-950/20 transition-colors disabled:opacity-40"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button
                          title="Request Info"
                          disabled={actingId === item.id}
                          onClick={(e) => { e.stopPropagation(); handleRequestInfo(item.id) }}
                          className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-950/20 transition-colors disabled:opacity-40"
                        >
                          <HelpCircle className="h-4 w-4" />
                        </button>
                        <button
                          title="Escalate"
                          disabled={actingId === item.id}
                          onClick={(e) => { e.stopPropagation(); handleEscalate(item.id) }}
                          className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
                        >
                          <ArrowUpCircle className="h-4 w-4" />
                        </button>
                        <button
                          title="Assign to Me"
                          disabled={actingId === item.id}
                          onClick={(e) => { e.stopPropagation(); handleAssign(item.id) }}
                          className="p-1.5 rounded-lg text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/20 transition-colors disabled:opacity-40"
                        >
                          <UserCheck className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Context Panel */}
      {selectedItem && (
        <div className="w-2/5 overflow-auto card">
          <div className="px-5 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Context</h3>
              <button onClick={() => setSelectedItem(null)} aria-label="Close" className="p-1 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <XCircle className="h-4 w-4" />
              </button>
            </div>
          </div>
          <div className="space-y-4 p-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Project</p>
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">{selectedItem.projectName}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Issue</p>
              <p className="text-sm text-surface-700 dark:text-surface-300">{selectedItem.reason}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Confidence Score</p>
              <div className="mt-1 h-2 w-full rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                <div
                  className={`h-2 rounded-full ${selectedItem.confidence < 0.85 ? 'bg-red-500' : 'bg-primary-500'}`}
                  style={{ width: `${selectedItem.confidence * 100}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-surface-500">{Math.round(selectedItem.confidence * 100)}%</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Financial Impact</p>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">${selectedItem.financialImpact.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Suggested Action</p>
              <p className="text-sm text-primary-600 dark:text-primary-400">{selectedItem.suggestedAction}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Time in Queue</p>
              <p className="text-sm text-surface-700 dark:text-surface-300">{selectedItem.hoursInQueue} hours</p>
            </div>

            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Activity Log</p>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <div className="h-1.5 w-1.5 rounded-full bg-primary-500" />
                  <span className="text-surface-600 dark:text-surface-300">Item created — {new Date(selectedItem.createdAt).toLocaleString()}</span>
                </div>
                {selectedItem.resolvedAt && (
                  <div className="flex items-center gap-2 text-xs">
                    <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                    <span className="text-surface-600 dark:text-surface-300">Resolved — {new Date(selectedItem.resolvedAt).toLocaleString()}</span>
                  </div>
                )}
                <div className="flex items-center gap-2 text-xs">
                  <div className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                  <span className="text-surface-600 dark:text-surface-300">Current status: {selectedItem.status}</span>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => handleApprove(selectedItem.id)}
                disabled={actingId === selectedItem.id}
                className="flex-1 rounded-xl bg-primary-600 px-3 py-2 text-sm font-medium text-white hover:bg-primary-500 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                Approve
              </button>
              <button
                onClick={() => handleRequestInfo(selectedItem.id)}
                disabled={actingId === selectedItem.id}
                className="flex-1 rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                Request Info
              </button>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleEscalate(selectedItem.id)}
                disabled={actingId === selectedItem.id}
                className="flex-1 rounded-xl bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-500 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                Escalate
              </button>
              <button
                onClick={() => handleAssign(selectedItem.id)}
                disabled={actingId === selectedItem.id}
                className="flex-1 rounded-xl bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 active:scale-[0.98] transition-all disabled:opacity-50"
              >
                Assign to Me
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
