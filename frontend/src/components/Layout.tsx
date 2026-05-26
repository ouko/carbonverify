import { Outlet, Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard,
  FolderOpen,
  Database,
  Calculator,
  FileText,
  ClipboardList,
  Menu,
  X,
  Sun,
  Moon,
  LogOut,
  Shield,
  Landmark,
  BarChart3,
  Leaf,
  Coins,
  Building2,
  Command,
  Target,
  MapPin,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'

const navGroups = [
  {
    label: 'Core',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/projects', icon: FolderOpen, label: 'Projects' },
      { to: '/data-sources', icon: Database, label: 'Data Sources' },
      { to: '/calculations', icon: Calculator, label: 'Calculations' },
      { to: '/reports', icon: FileText, label: 'Reports' },
      { to: '/review-queue', icon: ClipboardList, label: 'Review Queue' },
      { to: '/field', icon: MapPin, label: 'Field' },
    ],
  },
  {
    label: 'Marketplace',
    items: [
      { to: '/leads', icon: Target, label: 'Lead Intelligence' },
      { to: '/brokerage', icon: BarChart3, label: 'Brokerage' },
      { to: '/tokenization', icon: Coins, label: 'Tokenization' },
      { to: '/corporate', icon: Building2, label: 'Corporate' },
    ],
  },
  {
    label: 'Security',
    items: [
      { to: '/security', icon: Shield, label: 'Security' },
      { to: '/audit', icon: Landmark, label: 'Audit' },
      { to: '/compliance', icon: Leaf, label: 'Compliance' },
    ],
  },
  {
    label: 'Operations',
    items: [
      { to: '/command-center', icon: Command, label: 'Command Center' },
    ],
  },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const { isDark, toggle } = useThemeStore()

  return (
    <div className="flex h-screen bg-surface-50 dark:bg-surface-950 ambient-bg">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-surface-950/20 backdrop-blur-sm lg:hidden animate-fade-in"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 flex flex-col sidebar-glass
          transition-transform duration-300 ease-spring lg:static lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 h-16 border-b border-surface-100/50 dark:border-surface-800/30">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary-500 text-white">
            <Leaf className="w-5 h-5" />
          </div>
          <span className="text-lg font-bold tracking-tight text-surface-900 dark:text-surface-100">
            CarbonVerify
          </span>
          <button
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
            className="ml-auto p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto scrollbar-thin px-3 py-4 space-y-6 relative z-10">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="section-title px-3 mb-2">{group.label}</div>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)
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
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom actions */}
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
                {user?.email || ''}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggle}
              className="btn-ghost flex-1 justify-center text-xs py-2"
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
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

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="flex items-center h-16 px-4 lg:px-8 header-glass z-20">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="p-2 -ml-2 rounded-xl text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-800 lg:hidden"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="page-title ml-2 lg:ml-0">
            {navGroups.flatMap((g) => g.items).find((n) => n.to === location.pathname)?.label || 'CarbonVerify'}
          </h1>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto scrollbar-thin p-4 lg:p-8">
          <div className="animate-slide-up">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
