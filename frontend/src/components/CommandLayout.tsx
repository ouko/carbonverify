import { Outlet, Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  Inbox,
  LayoutGrid,
  GitPullRequest,
  BarChart3,
  Bot,
  Settings,
  Menu,
  X,
  Bell,
  Search,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'
import { useNotificationStore } from '../stores/notificationStore'
import { NotificationCenter } from './NotificationCenter'

const navItems = [
  { to: '/command-center/inbox', icon: Inbox, label: 'Inbox', badgeKey: 'inbox' },
  { to: '/command-center/projects', icon: LayoutGrid, label: 'Projects', badgeKey: 'projects' },
  { to: '/command-center/vvb', icon: GitPullRequest, label: 'VVB Pipeline', badgeKey: 'vvb' },
  { to: '/command-center/quality', icon: BarChart3, label: 'Quality Metrics', badgeKey: 'quality' },
  { to: '/command-center/agents', icon: Bot, label: 'Agent Performance', badgeKey: 'agents' },
  { to: '/command-center/settings', icon: Settings, label: 'Settings', badgeKey: 'settings' },
]

export default function CommandLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const { isDark, toggle } = useThemeStore()
  const unreadCount = useNotificationStore((s) => s.unreadCount)

  const currentLabel = navItems.find((n) => location.pathname.startsWith(n.to))?.label || 'Command Center'

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-900">
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform border-r border-gray-200 bg-white transition-transform dark:border-gray-700 dark:bg-gray-800 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between px-4">
          <div>
            <span className="text-lg font-bold text-indigo-600 dark:text-indigo-400">Command</span>
            <span className="text-lg font-bold text-gray-800 dark:text-gray-200">Center</span>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="px-3 py-2">
          <div className="flex items-center rounded-lg bg-gray-100 px-3 py-2 dark:bg-gray-700">
            <Search className="h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search projects..."
              className="ml-2 w-full bg-transparent text-sm text-gray-700 outline-none placeholder:text-gray-400 dark:text-gray-200"
            />
          </div>
        </div>

        <nav className="mt-2 space-y-0.5 px-2">
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-300'
                    : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
              >
                <item.icon className="mr-3 h-5 w-5" />
                {item.label}
                {item.label === 'Inbox' && unreadCount > 0 && (
                  <span className="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-xs font-bold text-white">
                    {unreadCount}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        <div className="absolute bottom-0 w-full border-t border-gray-200 p-3 dark:border-gray-700">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs">
              <p className="font-medium text-gray-700 dark:text-gray-200">{user?.name || 'Operator'}</p>
              <p className="text-gray-500 dark:text-gray-400">{user?.role || 'operator'}</p>
            </div>
            <button
              onClick={toggle}
              className="rounded p-1.5 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
              title="Toggle theme"
            >
              {isDark ? <span className="text-sm">☀️</span> : <span className="text-sm">🌙</span>}
            </button>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center">
            <button onClick={() => setSidebarOpen(true)} className="mr-3 lg:hidden">
              <Menu className="h-5 w-5 text-gray-500" />
            </button>
            <h1 className="text-base font-semibold text-gray-800 dark:text-gray-100">{currentLabel}</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative rounded-full p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute right-1 top-1 h-4 w-4 rounded-full bg-red-500 text-center text-[10px] font-bold leading-4 text-white">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
          </div>
        </header>

        {notificationsOpen && (
          <div className="absolute right-4 top-14 z-50 w-96">
            <NotificationCenter onClose={() => setNotificationsOpen(false)} />
          </div>
        )}

        <main className="flex-1 overflow-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
