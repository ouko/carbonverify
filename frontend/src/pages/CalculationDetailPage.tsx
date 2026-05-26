import { useParams } from 'react-router-dom'
import { ArrowLeft, Calculator, Calendar, Activity, BarChart3, Shield, Target } from 'lucide-react'
import { Link } from 'react-router-dom'
import LoadingSpinner from '../components/LoadingSpinner'
import Breadcrumbs from '../components/Breadcrumbs'
import { useCalculation } from '../hooks/useCalculations'

const statusBadge: Record<string, string> = {
  draft: 'badge-slate',
  review_pending: 'badge-amber',
  approved: 'badge-green',
  rejected: 'badge-red',
}

export default function CalculationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: calc, isLoading, isError, error } = useCalculation(id || '')

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

  if (!calc) {
    return (
      <div className="card p-12 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <Calculator className="w-6 h-6 text-surface-400 dark:text-surface-500" />
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400">Calculation not found.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: 'Home', to: '/' }, { label: 'Calculations', to: '/calculations' }, { label: calc.id }]} />
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/calculations"
          aria-label="Go back"
          className="btn-ghost p-2"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="page-title">Calculation</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge ${statusBadge[calc.status] || 'badge-slate'}`}>
              {(calc.status || '').replace('_', ' ')}
            </span>
            <span className="text-xs text-surface-400 dark:text-surface-500 font-mono">{calc.project_id.slice(0, 8)}...</span>
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
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Status</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 capitalize">{(calc.status || '').replace('_', ' ')}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
              <BarChart3 className="w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Emissions Reduced</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">
            {calc.emissions_reduction_tCO2e?.toLocaleString() ?? 'N/A'} <span className="text-sm font-medium text-surface-500">tCO2e</span>
          </p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <Shield className="w-4.5 h-4.5 text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Confidence</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-primary-500"
                style={{ width: `${Math.round((calc.confidence_score || 0) * 100)}%` }}
              />
            </div>
            <span className="text-sm font-bold text-surface-900 dark:text-surface-100 tabular-nums">
              {Math.round((calc.confidence_score || 0) * 100)}%
            </span>
          </div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/30 flex items-center justify-center">
              <Target className="w-4.5 h-4.5 text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Compliance</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-amber-500"
                style={{ width: `${Math.round((calc.methodology_compliance_score || 0) * 100)}%` }}
              />
            </div>
            <span className="text-sm font-bold text-surface-900 dark:text-surface-100 tabular-nums">
              {Math.round((calc.methodology_compliance_score || 0) * 100)}%
            </span>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="card p-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-4">Calculation Details</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1">
            <p className="text-xs text-surface-400 dark:text-surface-500">Project ID</p>
            <p className="text-sm font-mono text-surface-700 dark:text-surface-300">{calc.project_id}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-surface-400 dark:text-surface-500">Monitoring Period</p>
            <div className="flex items-center gap-1.5 text-sm text-surface-700 dark:text-surface-300">
              <Calendar className="w-3.5 h-3.5 text-surface-400" />
              {calc.monitoring_period_start} → {calc.monitoring_period_end}
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-surface-400 dark:text-surface-500">fNRB Value</p>
            <p className="text-sm font-semibold text-surface-700 dark:text-surface-300">{calc.fNRB_value ?? 'N/A'}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-surface-400 dark:text-surface-500">Uncertainty (95% CI)</p>
            <p className="text-sm font-semibold text-surface-700 dark:text-surface-300">{calc.uncertainty_95CI ?? 'N/A'}</p>
          </div>
          <div className="space-y-1 sm:col-span-2 lg:col-span-2">
            <p className="text-xs text-surface-400 dark:text-surface-500">Leakage Assessment</p>
            <pre className="text-xs font-mono text-surface-600 dark:text-surface-400 bg-surface-100 dark:bg-surface-800 p-2 rounded-lg overflow-x-auto">
              {calc.leakage_assessment ? JSON.stringify(calc.leakage_assessment, null, 2) : 'N/A'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  )
}
