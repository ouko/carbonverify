import { Users, Activity, Shield, UserCheck, UserX, Lock, TrendingUp } from 'lucide-react'
import { useAdminStats } from '../../hooks/useAdmin'
import LoadingSpinner from '../../components/LoadingSpinner'

export default function AdminDashboardPage() {
  const { data: stats, isLoading, isError } = useAdminStats()

  if (isLoading) return <LoadingSpinner />
  if (isError) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load admin stats</p>
      </div>
    )
  }

  const statCards = [
    { label: 'Total Users', value: stats?.total_users ?? 0, icon: Users, color: 'text-primary-500', bg: 'bg-primary-50 dark:bg-primary-950/20' },
    { label: 'Active Users', value: stats?.active_users ?? 0, icon: UserCheck, color: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/20' },
    { label: 'Inactive Users', value: stats?.inactive_users ?? 0, icon: UserX, color: 'text-surface-500', bg: 'bg-surface-100 dark:bg-surface-800/50' },
    { label: 'Locked Accounts', value: stats?.locked_users ?? 0, icon: Lock, color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-950/20' },
    { label: 'Active Sessions', value: stats?.total_sessions ?? 0, icon: Activity, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/20' },
    { label: 'MFA Enabled', value: stats?.mfa_enabled_count ?? 0, icon: Shield, color: 'text-violet-500', bg: 'bg-violet-50 dark:bg-violet-950/20' },
  ]

  const roleColors: Record<string, string> = {
    admin: 'bg-red-100 text-red-700 dark:bg-red-950/30 dark:text-red-300',
    operator: 'bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300',
    developer: 'bg-blue-100 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300',
    viewer: 'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400',
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="page-title">Admin Dashboard</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
          System overview and user analytics
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {statCards.map((card) => (
          <div key={card.label} className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-9 h-9 rounded-xl ${card.bg} flex items-center justify-center`}>
                <card.icon className={`w-4.5 h-4.5 ${card.color}`} />
              </div>
              <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">
                {card.label}
              </span>
            </div>
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{card.value}</p>
          </div>
        ))}
      </div>

      {/* New users */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-primary-500" />
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">New Users</h3>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4 text-center">
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.new_users_today ?? 0}</p>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">Today</p>
            </div>
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4 text-center">
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.new_users_this_week ?? 0}</p>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">This Week</p>
            </div>
          </div>
        </div>

        {/* Role distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100 mb-4">Role Distribution</h3>
          <div className="space-y-3">
            {Object.entries(stats?.users_by_role ?? {}).map(([role, count]) => (
              <div key={role} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`badge ${roleColors[role] || 'badge-slate'} text-[10px] capitalize`}>{role}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-24 h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary-500"
                      style={{ width: `${stats?.total_users ? (count / stats.total_users) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold text-surface-900 dark:text-surface-100 w-6 text-right">{count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
