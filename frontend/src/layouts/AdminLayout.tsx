import { Outlet, Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard,
  Users,
  Activity,
  Settings,
  Menu,
  X,
  Sun,
  Moon,
  LogOut,
  Leaf,
  ChevronLeft,
  Key,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'

const adminNavItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/users', icon: Users, label: 'Users' },
  { to: '/admin/sessions', icon: Activity, label: 'Sessions' },
  { to: '/admin/api-keys', icon: Key, label: 'API Keys' },
  { to: '/admin/settings', icon: Settings, label: 'Settings' },
]

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const { isDark, toggle } = useThemeStore()

  return (
    <div className="flex h-screen bg-surface-50 dark:bg-surface-950 ambient-bg">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-surface-950/20 backdrop-blur-sm lg:hidden animate-fade-in"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 flex flex-col sidebar-glass
          transition-transform duration-300 ease-spring lg:static lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center gap-3 px-5 h-16 border-b border-surface-100/50 dark:border-surface-800/30">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-500 text-white">
            <Leaf className="w-5 h-5" />
          </div>
          <span className="text-lg font-bold tracking-tight text-surface-900 dark:text-surface-100">
            Admin
          </span>
          <button
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
            className="ml-auto p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-3 pt-3">
          <Link
            to="/"
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-surface-500 hover:text-surface-700 hover:bg-surface-100 dark:text-surface-400 dark:hover:text-surface-200 dark:hover:bg-surface-800 transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Back to CarbonVerify
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto scrollbar-thin px-3 py-4 space-y-1 relative z-10">
          {adminNavItems.map((item) => {
            const isActive = location.pathname === item.to || (item.to !== '/admin' && location.pathname.startsWith(`${item.to}/`))
            return (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={isActive ? 'nav-item-active' : 'nav-item'}
              >
                <item.icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 2.5 : 2} />
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="p-3 border-t border-surface-100/50 dark:border-surface-800/30 relative z-10">
          <div className="flex items-center gap-2 mb-2 px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-primary-700 dark:text-primary-300 text-sm font-semibold">
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-surface-900 dark:text-surface-200 truncate">
                {user?.name || 'User'}
              </div>
              <div className="text-xs text-surface-400 dark:text-surface-500 truncate">
                {user?.role || ''}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggle}
              className="btn-ghost flex-1 justify-center text-xs py-2"
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button
              onClick={logout}
              className="btn-ghost flex-1 justify-center text-xs py-2 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
              aria-label="Log out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <header className="flex items-center h-16 px-4 lg:px-8 header-glass z-20">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="p-2 -ml-2 rounded-xl text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="page-title ml-2 lg:ml-0">
            {adminNavItems.find((n) => n.to === location.pathname)?.label || 'Admin'}
          </h1>
        </header>
        <main className="flex-1 overflow-auto scrollbar-thin p-4 lg:p-8">
          <div className="animate-slide-up">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
