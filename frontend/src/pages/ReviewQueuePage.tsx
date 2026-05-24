import { ClipboardList, User } from 'lucide-react'
import { useReviewQueue } from '../hooks/useReviewQueue'

const priorityColors: Record<number, string> = {
  1: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  2: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  3: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  4: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  5: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

const statusBadge: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  in_review: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  resolved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  escalated: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

export default function ReviewQueuePage() {
  const { data: items, isLoading } = useReviewQueue()

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 dark:bg-gray-700/50 dark:text-gray-400">
              <tr>
                <th className="px-6 py-3 font-medium">Item Type</th>
                <th className="px-6 py-3 font-medium">Reason</th>
                <th className="px-6 py-3 font-medium">Priority</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Assigned To</th>
                <th className="px-6 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {items?.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <ClipboardList className="h-4 w-4 text-primary-600 dark:text-primary-400" />
                      <span className="font-medium text-gray-900 dark:text-gray-100 capitalize">
                        {item.item_type.replace('_', ' ')}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 max-w-xs truncate text-gray-600 dark:text-gray-300">
                    {item.reason}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${priorityColors[item.priority]}`}>
                      P{item.priority}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge[item.status]}`}>
                      {item.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {item.assigned_to ? (
                      <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
                        <User className="h-3.5 w-3.5" />
                        <span className="font-mono text-xs">{item.assigned_to.slice(0, 8)}...</span>
                      </div>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-500">Unassigned</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                    {new Date(item.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {items?.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                    No review queue items found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
