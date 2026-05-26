import { useNavigate } from 'react-router-dom'
import { FolderOpen, ClipboardList, Calculator, Leaf, TrendingUp, ArrowUpRight, Target } from 'lucide-react'
import { useLeadsStats } from '../hooks/useLeads'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, AreaChart, Area } from 'recharts'
import StatCard from '../components/StatCard'
import LoadingSpinner from '../components/LoadingSpinner'
import { useDashboardStats } from '../hooks/useDashboardStats'

const statusColors: Record<string, string> = {
  onboarding: '#94a3b8',
  data_collection: '#3b82f6',
  calculation: '#f59e0b',
  review: '#8b5cf6',
  submitted: '#10b981',
  verified: '#059669',
  monitoring: '#06b6d4',
}

const statusLabels: Record<string, string> = {
  onboarding: 'Onboarding',
  data_collection: 'Data Collection',
  calculation: 'Calculation',
  review: 'Review',
  submitted: 'Submitted',
  verified: 'Verified',
  monitoring: 'Monitoring',
}

const emissionsTrend = [
  { month: 'Jan', value: 1200 },
  { month: 'Feb', value: 1850 },
  { month: 'Mar', value: 2400 },
  { month: 'Apr', value: 2100 },
  { month: 'May', value: 3200 },
  { month: 'Jun', value: 3800 },
]

export default function DashboardPage() {
  const navigate = useNavigate()
  const { data: stats, isLoading, isError, error } = useDashboardStats()
  const { data: leadStats } = useLeadsStats()

  const chartData = stats
    ? Object.entries(stats.projects_by_status).map(([key, value]) => ({
        name: statusLabels[key] || key,
        value,
        color: statusColors[key] || '#94a3b8',
      }))
    : []

  if (isLoading) {
    return (
      <LoadingSpinner />
    )
  }

  if (isError) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
        <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Welcome */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="page-title">Dashboard</h2>
          <p className="text-surface-500 dark:text-surface-400 mt-1 text-sm">
            Overview of your carbon credit verification pipeline
          </p>
        </div>
        <button onClick={() => navigate('/projects/new')} className="btn-primary text-sm">
          <ArrowUpRight className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          title="Total Projects"
          value={stats?.total_projects ?? 0}
          icon={<FolderOpen className="h-5 w-5" />}
          color="emerald"
          trend={{ value: 12, positive: true }}
          subtitle="Across all methodologies"
          delay={0}
        />
        <StatCard
          title="Pending Reviews"
          value={stats?.pending_reviews ?? 0}
          icon={<ClipboardList className="h-5 w-5" />}
          color="amber"
          trend={{ value: 3, positive: false }}
          subtitle="Awaiting quality control"
          delay={100}
        />
        <StatCard
          title="Calculations"
          value={stats?.recent_calculations ?? 0}
          icon={<Calculator className="h-5 w-5" />}
          color="blue"
          trend={{ value: 8, positive: true }}
          subtitle="This month"
          delay={200}
        />
        <StatCard
          title="High Priority Leads"
          value={leadStats?.high_priority_count ?? 0}
          icon={<Target className="h-5 w-5" />}
          color="violet"
          trend={{ value: 4, positive: true }}
          subtitle="From registry scraping"
          delay={250}
        />
        <StatCard
          title="Emissions Reduced"
          value={`${(stats?.total_emissions_reduced ?? 0).toLocaleString()} t`}
          icon={<Leaf className="h-5 w-5" />}
          color="rose"
          trend={{ value: 24, positive: true }}
          subtitle="CO2e equivalent"
          delay={300}
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Projects Bar Chart */}
        <div className="lg:col-span-3 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">Projects by Status</h3>
              <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">Current pipeline distribution</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-surface-400">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Live data</span>
            </div>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barSize={36}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: 'currentColor', fontSize: 11, opacity: 0.5 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: 'currentColor', fontSize: 11, opacity: 0.5 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'currentColor', opacity: 0.04, radius: 8 }}
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
                  }}
                  itemStyle={{ color: '#f8fafc' }}
                  labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Emissions Trend */}
        <div className="lg:col-span-2 card p-6">
          <div className="mb-6">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">Emissions Trend</h3>
            <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">tCO2e reduced per month</p>
          </div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={emissionsTrend}>
                <defs>
                  <linearGradient id="emissionsGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis
                  dataKey="month"
                  tick={{ fill: 'currentColor', fontSize: 11, opacity: 0.5 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: 'currentColor', fontSize: 11, opacity: 0.5 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  fill="url(#emissionsGradient)"
                  dot={{ fill: '#10b981', strokeWidth: 2, r: 4, stroke: '#fff' }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Start Calculation', desc: 'Run MRV pipeline', icon: Calculator, to: '/calculations' },
          { label: 'Review Queue', desc: `${stats?.pending_reviews ?? 0} items pending`, icon: ClipboardList, to: '/review-queue' },
          { label: 'Lead Intelligence', desc: `${leadStats?.high_priority_count ?? 0} high-priority leads`, icon: Target, to: '/leads' },
          { label: 'Generate Report', desc: 'Create VVB package', icon: FolderOpen, to: '/reports' },
        ].map((action, i) => (
          <button
            key={action.label}
            onClick={() => navigate(action.to)}
            className="card-hover p-5 text-left group"
            style={{ animationDelay: `${400 + i * 100}ms` }}
          >
            <action.icon className="w-5 h-5 text-primary-500 mb-3 group-hover:scale-110 transition-transform duration-300" />
            <div className="text-sm font-semibold text-surface-900 dark:text-surface-100">{action.label}</div>
            <div className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">{action.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
