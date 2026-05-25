import { useState } from 'react'
import { ClipboardList, User, Inbox, CheckCircle, ArrowUpCircle, UserCheck, Check } from 'lucide-react'
import { useReviewQueue, updateReviewQueueItem } from '../hooks/useReviewQueue'
import { useQueryClient } from '@tanstack/react-query'

const priorityColors: Record<number, string> = {
  1: 'badge-slate',
  2: 'badge-blue',
  3: 'badge-amber',
  4: 'bg-orange-50 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300',
  5: 'badge-red',
}

const statusBadge: Record<string, string> = {
  pending: 'badge-slate',
  in_review: 'badge-blue',
  resolved: 'badge-green',
  escalated: 'badge-red',
}

export default function ReviewQueuePage() {
  const qc = useQueryClient()
  const { data: items, isLoading } = useReviewQueue()
  const [actingId, setActingId] = useState<string | null>(null)

  const handleApprove = (id: string) => {
    setActingId(id)
    setTimeout(() => {
      updateReviewQueueItem(id, { status: 'resolved', resolved_at: new Date().toISOString() })
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
      setActingId(null)
    }, 400)
  }

  const handleEscalate = (id: string) => {
    setActingId(id)
    setTimeout(() => {
      updateReviewQueueItem(id, { status: 'escalated' })
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      setActingId(null)
    }, 400)
  }

  const handleAssign = (id: string) => {
    setActingId(id)
    setTimeout(() => {
      updateReviewQueueItem(id, { assigned_to: 'current.user@carbonverify.io', status: 'in_review' })
      qc.invalidateQueries({ queryKey: ['review-queue'] })
      setActingId(null)
    }, 400)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="page-title">Review Queue</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
          Human-in-the-loop quality assurance items
        </p>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="relative">
            <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
            <div className="absolute inset-0 h-10 w-10 rounded-full border-[3px] border-transparent border-b-primary-300/30 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
          </div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Item Type</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Reason</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Priority</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Assigned</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Created</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {items?.map((item) => (
                  <tr
                    key={item.id}
                    className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                          <ClipboardList className="w-4 h-4 text-primary-500 dark:text-primary-400" />
                        </div>
                        <span className="font-semibold text-surface-900 dark:text-surface-100 capitalize">
                          {item.item_type.replace('_', ' ')}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 max-w-xs">
                      <span className="text-surface-600 dark:text-surface-300 text-sm line-clamp-1">
                        {item.reason}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${priorityColors[item.priority] || 'badge-slate'}`}>
                        P{item.priority}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${statusBadge[item.status] || 'badge-slate'}`}>
                        {item.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {item.assigned_to ? (
                        <div className="flex items-center gap-1.5 text-surface-600 dark:text-surface-300">
                          <User className="h-3.5 w-3.5 text-surface-400" />
                          <span className="font-mono text-xs bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded">{item.assigned_to.slice(0, 8)}...</span>
                        </div>
                      ) : (
                        <span className="text-xs text-surface-400 dark:text-surface-500 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-surface-500 dark:text-surface-400">
                      {new Date(item.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-center gap-1">
                        {item.status !== 'resolved' && (
                          <button
                            title="Approve"
                            disabled={actingId === item.id}
                            onClick={() => handleApprove(item.id)}
                            className="p-1.5 rounded-lg text-primary-600 hover:bg-primary-50 dark:text-primary-400 dark:hover:bg-primary-950/20 transition-colors disabled:opacity-40"
                          >
                            {actingId === item.id ? <Check className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                          </button>
                        )}
                        {item.status !== 'escalated' && (
                          <button
                            title="Escalate"
                            disabled={actingId === item.id}
                            onClick={() => handleEscalate(item.id)}
                            className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
                          >
                            <ArrowUpCircle className="h-4 w-4" />
                          </button>
                        )}
                        {!item.assigned_to && (
                          <button
                            title="Assign to Me"
                            disabled={actingId === item.id}
                            onClick={() => handleAssign(item.id)}
                            className="p-1.5 rounded-lg text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/20 transition-colors disabled:opacity-40"
                          >
                            <UserCheck className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {items?.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                          <Inbox className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                        </div>
                        <div className="text-sm text-surface-500 dark:text-surface-400">No review queue items found.</div>
                      </div>
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
