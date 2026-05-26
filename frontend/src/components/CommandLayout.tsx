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
  Sun,
  Moon,
  LogOut,
  ArrowLeft,
  Leaf,
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
  const [searchText, setSearchText] = useState('')
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const { isDark, toggle } = useThemeStore()
  const unreadCount = useNotificationStore((s) => s.unreadCount)

  const currentLabel = navItems.find((n) => location.pathname.startsWith(n.to))?.label || 'Command Center'

  return (
    <div className="flex h-screen bg-surface-50 dark:bg-surface-950">
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-surface-950/20 backdrop-blur-sm lg:hidden animate-fade-in" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 flex flex-col
          bg-white/95 dark:bg-surface-900/95 backdrop-blur-xl
          border-r border-surface-200/60 dark:border-surface-800/40
          transition-transform duration-300 ease-spring lg:static lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-5 h-16 border-b border-surface-100 dark:border-surface-800/50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-surface-900 dark:text-surface-100">Command</span>
              <span className="text-lg font-bold tracking-tight text-primary-600 dark:text-primary-400">Center</span>
            </div>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3 pb-2">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <Leaf className="h-3.5 w-3.5 text-primary-500" />
            CarbonVerify
          </Link>
        </div>

        <div className="px-3 py-3">
          <div className="flex items-center rounded-xl bg-surface-100/80 dark:bg-surface-800/50 px-3.5 py-2.5">
            <Search className="h-4 w-4 text-surface-400" />
            <input
              type="text"
              placeholder="Search projects..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="ml-2 w-full bg-transparent text-sm text-surface-700 outline-none placeholder:text-surface-400 dark:text-surface-200"
            />
          </div>
          {searchText && (
            <p className="mt-1.5 px-1 text-xs text-surface-400 dark:text-surface-500">
              Search: {searchText}
            </p>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto scrollbar-thin px-2 space-y-0.5">
          {navItems.map((item) => {
            const active = location.pathname.startsWith(item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={active ? 'nav-item-active' : 'nav-item'}
              >
                <item.icon className="h-[18px] w-[18px]" strokeWidth={active ? 2.5 : 2} />
                {item.label}
                {item.label === 'Inbox' && unreadCount > 0 && (
                  <span className="ml-auto rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-bold text-white">
                    {unreadCount}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        <div className="p-3 border-t border-surface-100 dark:border-surface-800/50">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs">
              <p className="font-semibold text-surface-700 dark:text-surface-200">{user?.name || 'Operator'}</p>
              <p className="text-surface-400 dark:text-surface-500 capitalize">{user?.role || 'operator'}</p>
            </div>
            <button
              onClick={toggle}
              className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
              title="Toggle theme"
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/20 transition-colors"
          >
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-surface-200/60 dark:border-surface-800/40 bg-white/50 dark:bg-surface-950/50 backdrop-blur-sm px-4 lg:px-6">
          <div className="flex items-center">
            <button onClick={() => setSidebarOpen(true)} className="p-2 -ml-2 rounded-xl text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden transition-colors">
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="text-base font-semibold text-surface-900 dark:text-surface-100 ml-2 lg:ml-0">{currentLabel}</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative p-2 rounded-xl text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
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

        <main className="flex-1 overflow-auto scrollbar-thin p-4 lg:p-6">
          <div className="animate-slide-up">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
