import { FolderOpen, ClipboardList, Calculator, Leaf } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import StatCard from '../components/StatCard'
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

export default function DashboardPage() {
  const { data: stats, isLoading } = useDashboardStats()

  const chartData = stats
    ? Object.entries(stats.projects_by_status).map(([key, value]) => ({
        name: statusLabels[key] || key,
        value,
        color: statusColors[key] || '#94a3b8',
      }))
    : []

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Projects"
          value={stats?.total_projects ?? 0}
          icon={<FolderOpen className="h-6 w-6" />}
          color="primary"
        />
        <StatCard
          title="Pending Reviews"
          value={stats?.pending_reviews ?? 0}
          icon={<ClipboardList className="h-6 w-6" />}
          color="amber"
        />
        <StatCard
          title="Calculations"
          value={stats?.recent_calculations ?? 0}
          icon={<Calculator className="h-6 w-6" />}
          color="blue"
        />
        <StatCard
          title="Emissions Reduced (tCO2e)"
          value={stats?.total_emissions_reduced?.toLocaleString() ?? 0}
          icon={<Leaf className="h-6 w-6" />}
          color="rose"
        />
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-100">
          Projects by Status
        </h2>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: '0.5rem',
                }}
                labelStyle={{ color: '#e5e7eb' }}
                itemStyle={{ color: '#e5e7eb' }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
