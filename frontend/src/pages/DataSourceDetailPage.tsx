import { useParams } from 'react-router-dom'
import { ArrowLeft, Database, CheckCircle, AlertTriangle, XCircle, Clock, Calendar, Activity, FileJson } from 'lucide-react'
import { Link } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner'
import { useDataSource } from '../hooks/useDataSources'

const statusColor: Record<string, string> = {
  pending: 'badge-amber',
  valid: 'badge-green',
  flagged: 'bg-orange-50 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300',
  rejected: 'badge-red',
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="h-3.5 w-3.5 text-amber-500" />,
  valid: <CheckCircle className="h-3.5 w-3.5 text-primary-500" />,
  flagged: <AlertTriangle className="h-3.5 w-3.5 text-orange-500" />,
  rejected: <XCircle className="h-3.5 w-3.5 text-red-500" />,
}

export default function DataSourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: source, isLoading, isError, error } = useDataSource(id || '')

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

  if (!source) {
    return (
      <div className="card p-12 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <Database className="w-6 h-6 text-surface-400 dark:text-surface-500" />
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400">Data source not found.</p>
        </div>
      </div>
    )
  }

  const displayName = `${source.schema_version} ${(source.source_type || '').replace('_', ' ')}`

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/data-sources"
          className="btn-ghost p-2"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="page-title capitalize">{displayName}</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge inline-flex items-center gap-1.5 ${statusColor[source.validation_status] || 'badge-slate'}`}>
              {statusIcons[source.validation_status]}
              {source.validation_status}
            </span>
            <span className="text-xs text-surface-400 dark:text-surface-500">{source.schema_version}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Database className="w-4.5 h-4.5 text-primary-600 dark:text-primary-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Source Type</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 capitalize">{(source.source_type || '').replace('_', ' ')}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Status</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 capitalize">{source.validation_status}</p>
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
                style={{ width: `${Math.round(((source as any).confidence_score || 0) * 100)}%` }}
              />
            </div>
            <span className="text-sm font-bold text-surface-900 dark:text-surface-100 tabular-nums">
              {Math.round(((source as any).confidence_score || 0) * 100)}%
            </span>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/30 flex items-center justify-center">
              <Calendar className="w-4.5 h-4.5 text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Created</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{new Date(source.created_at).toLocaleDateString()}</p>
        </div>
      </div>

      {/* Details */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4">Schema & Validation</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-surface-500 dark:text-surface-400">Schema Version</span>
              <span className="font-medium text-surface-900 dark:text-surface-100">{source.schema_version}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-surface-500 dark:text-surface-400">Source Type</span>
              <span className="font-medium text-surface-900 dark:text-surface-100 capitalize">{(source.source_type || '').replace('_', ' ')}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-surface-500 dark:text-surface-400">Validation Status</span>
              <span className={`badge inline-flex items-center gap-1.5 ${statusColor[source.validation_status] || 'badge-slate'}`}>
                {statusIcons[source.validation_status]}
                {source.validation_status}
              </span>
            </div>
            {source.validation_errors && source.validation_errors.length > 0 && (
              <div className="pt-2">
                <span className="text-surface-500 dark:text-surface-400 block mb-2">Validation Errors</span>
                <ul className="space-y-1">
                  {source.validation_errors.map((err, i) => (
                    <li key={i} className="text-red-600 dark:text-red-400 text-xs bg-red-50 dark:bg-red-950/30 px-2 py-1.5 rounded-md">{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        <div className="card p-6">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100 mb-4 flex items-center gap-2">
            <FileJson className="w-4 h-4 text-surface-400" />
            Raw Data
          </h3>
          <pre className="text-xs bg-surface-100 dark:bg-surface-800 rounded-lg p-4 overflow-auto max-h-80 text-surface-700 dark:text-surface-300">
            {JSON.stringify(source.raw_data, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  )
}
