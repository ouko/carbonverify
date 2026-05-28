import { useState, useEffect } from 'react'
import { ClipboardList, User, Inbox, CheckCircle, ArrowUpCircle, UserCheck, Check, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { useReviewQueue, useUpdateReviewQueueItem, useDeleteReviewQueueItem } from '../hooks/useReviewQueue'
import LoadingSpinner from '../components/LoadingSpinner'

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
  const [page, setPage] = useState(1)
  const perPage = 10
  const { data: items, isLoading, isError, error } = useReviewQueue()
  const updateMutation = useUpdateReviewQueueItem()
  const deleteMutation = useDeleteReviewQueueItem()
  const [actingId, setActingId] = useState<string | null>(null)

  const total = items?.length ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const currentPage = Math.min(page, totalPages)
  const paginated = items?.slice((currentPage - 1) * perPage, currentPage * perPage)

  useEffect(() => {
    setPage(1)
  }, [items])

  const handleApprove = (id: string) => {
    setActingId(id)
    updateMutation.mutate(
      {
        id,
        updates: { status: 'resolved', resolved_at: new Date().toISOString() },
      },
      { onSettled: () => setActingId(null) }
    )
  }

  const handleEscalate = (id: string) => {
    setActingId(id)
    updateMutation.mutate(
      { id, updates: { status: 'escalated' } },
      { onSettled: () => setActingId(null) }
    )
  }

  const handleAssign = (id: string) => {
    setActingId(id)
    updateMutation.mutate(
      { id, updates: { assigned_to: 'current.user@carbonverify.io', status: 'in_review' } },
      { onSettled: () => setActingId(null) }
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="page-title">Review Queue</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">Human-in-the-loop quality assurance items</p>
        </div>
        <LoadingSpinner />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="page-title">Review Queue</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">Human-in-the-loop quality assurance items</p>
        </div>
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load review queue</p>
          <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
        </div>
      </div>
    )
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
              {paginated?.map((item) => (
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
                        {(item.item_type || '').replace('_', ' ')}
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
                      {(item.status || '').replace('_', ' ')}
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
                          aria-label="Approve"
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
                          aria-label="Escalate"
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
                          aria-label="Assign to Me"
                          disabled={actingId === item.id}
                          onClick={() => handleAssign(item.id)}
                          className="p-1.5 rounded-lg text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/20 transition-colors disabled:opacity-40"
                        >
                          <UserCheck className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        title="Delete"
                        aria-label="Delete"
                        disabled={actingId === item.id}
                        onClick={() => {
                          if (window.confirm('Are you sure you want to delete this?')) {
                            deleteMutation.mutate(item.id)
                          }
                        }}
                        className="p-1.5 rounded-lg text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {paginated?.length === 0 && (
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
        {total > 0 && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-surface-200/60 dark:border-surface-800/40">
            <p className="text-xs text-surface-400 dark:text-surface-500">
              Showing {(currentPage - 1) * perPage + 1}-{Math.min(currentPage * perPage, total)} of {total}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" /> Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
