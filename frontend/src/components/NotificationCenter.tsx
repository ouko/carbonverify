import { X, AlertTriangle, Info, CheckCircle, AlertCircle } from 'lucide-react'
import { useNotificationStore } from '../stores/notificationStore'

export function NotificationCenter({ onClose }: { onClose: () => void }) {
  const { notifications, unreadCount, markRead, markAllRead, dismiss, clearAll } = useNotificationStore()

  const getIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <AlertTriangle className="h-4 w-4 text-red-500" />
      case 'warning': return <AlertCircle className="h-4 w-4 text-yellow-500" />
      default: return <Info className="h-4 w-4 text-blue-500" />
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          Notifications {unreadCount > 0 && <span className="text-indigo-600">({unreadCount})</span>}
        </h3>
        <div className="flex gap-1">
          <button onClick={markAllRead} className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700">
            Mark all read
          </button>
          <button onClick={clearAll} className="rounded px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700">
            Clear
          </button>
          <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="max-h-96 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
            No notifications
          </div>
        ) : (
          notifications.slice(0, 50).map((n) => (
            <div
              key={n.id}
              className={`flex items-start gap-3 border-b border-gray-100 px-4 py-3 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50 ${
                !n.read ? 'bg-gray-50/50 dark:bg-gray-700/30' : ''
              }`}
            >
              <div className="mt-0.5">{getIcon(n.severity)}</div>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${!n.read ? 'text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300'}`}>
                  {n.title}
                </p>
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{n.message}</p>
                <p className="mt-1 text-[10px] text-gray-400">
                  {new Date(n.timestamp).toLocaleTimeString()}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                {!n.read && (
                  <button onClick={() => markRead(n.id)} className="rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700" title="Mark read">
                    <CheckCircle className="h-3.5 w-3.5" />
                  </button>
                )}
                <button onClick={() => dismiss(n.id)} className="rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700" title="Dismiss">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
