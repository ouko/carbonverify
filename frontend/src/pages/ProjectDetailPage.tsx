import { useParams } from 'react-router-dom'
import { ArrowLeft, Database, Calculator, FileText, MapPin, Calendar, Activity } from 'lucide-react'
import { Link } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner'
import { useProject } from '../hooks/useProjects'

const statusColor: Record<string, string> = {
  onboarding: 'badge-slate',
  data_collection: 'badge-blue',
  calculation: 'badge-amber',
  review: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
  submitted: 'badge-green',
  verified: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  monitoring: 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/50 dark:text-cyan-300',
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading, isError, error } = useProject(id || '')

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

  if (!project) {
    return (
      <div className="card p-12 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <MapPin className="w-6 h-6 text-surface-400 dark:text-surface-500" />
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400">Project not found.</p>
        </div>
      </div>
    )
  }

  const quickLinks = [
    { to: '/data-sources', icon: Database, label: 'Data Sources', desc: 'View project data', color: 'from-primary-500/10 to-primary-600/5 text-primary-600 dark:text-primary-400' },
    { to: '/calculations', icon: Calculator, label: 'Calculations', desc: 'Review calculations', color: 'from-blue-500/10 to-blue-600/5 text-blue-600 dark:text-blue-400' },
    { to: '/reports', icon: FileText, label: 'Reports', desc: 'Generate reports', color: 'from-amber-500/10 to-amber-600/5 text-amber-600 dark:text-amber-400' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/projects"
          className="btn-ghost p-2"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="page-title">{project.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge ${statusColor[project.status] || 'badge-slate'}`}>
              {(project.status || '').replace('_', ' ')}
            </span>
            <span className="text-xs text-surface-400 dark:text-surface-500">{project.methodology}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-primary-600 dark:text-primary-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Methodology</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{project.methodology}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Status</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 capitalize">{(project.status || '').replace('_', ' ')}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Confidence</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-primary-500"
                style={{ width: `${Math.round((project.confidence_threshold || 0) * 100)}%` }}
              />
            </div>
            <span className="text-sm font-bold text-surface-900 dark:text-surface-100 tabular-nums">
              {Math.round((project.confidence_threshold || 0) * 100)}%
            </span>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/30 flex items-center justify-center">
              <Calendar className="w-4.5 h-4.5 text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Complexity</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{project.complexity_score ?? 'N/A'}</p>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid gap-4 sm:grid-cols-3">
        {quickLinks.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className="card-hover p-6 flex items-center gap-4 group"
          >
            <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${link.color} flex items-center justify-center transition-transform duration-300 group-hover:scale-110`}>
              <link.icon className="w-6 h-6" />
            </div>
            <div>
              <p className="font-semibold text-surface-900 dark:text-surface-100">{link.label}</p>
              <p className="text-sm text-surface-400 dark:text-surface-500">{link.desc}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
