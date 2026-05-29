import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Calendar, Activity, Hash, AlertCircle } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import Breadcrumbs from '../components/Breadcrumbs'
import { useReport } from '../hooks/useReports'

const statusColor: Record<string, string> = {
  draft: 'badge-slate',
  human_review: 'badge-amber',
  approved: 'badge-green',
  submitted: 'badge-blue',
  vvb_approved: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  rejected: 'badge-red',
}

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: report, isLoading, isError, error } = useReport(id || '')

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

  if (!report) {
    return (
      <div className="card p-12 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-surface-400 dark:text-surface-500" />
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400">Report not found.</p>
        </div>
      </div>
    )
  }

  const hasValidPdf = report.final_pdf && report.final_pdf.startsWith('http') && !report.final_pdf.includes('example.com')

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: 'Home', to: '/' }, { label: 'Reports', to: '/reports' }, { label: report.id }]} />
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/reports')}
          aria-label="Go back"
          className="btn-ghost p-2"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="page-title">Report</h1>
          <div className="flex items-center gap-2 mt-1">
            <span className={`badge ${statusColor[report.status] || 'badge-slate'}`}>
              {(report.status || '').replace('_', ' ')}
            </span>
            <span className="text-xs text-surface-400 dark:text-surface-500">{(report.template_type || '').replace('_', ' ')}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Hash className="w-4.5 h-4.5 text-primary-600 dark:text-primary-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Project ID</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 truncate" title={report.project_id}>
            {report.project_id.slice(0, 8)}...
          </p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Calculation Run</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 truncate" title={report.calculation_run_id}>
            {report.calculation_run_id.slice(0, 8)}...
          </p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 flex items-center justify-center">
              <FileText className="w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Template</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100 capitalize">{(report.template_type || '').replace('_', ' ')}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/30 flex items-center justify-center">
              <Calendar className="w-4.5 h-4.5 text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Created</span>
          </div>
          <p className="text-lg font-bold text-surface-900 dark:text-surface-100">
            {new Date(report.created_at).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* PDF Section */}
      <div className="card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-50 dark:bg-rose-950/30 flex items-center justify-center">
              <FileText className="w-5 h-5 text-rose-600 dark:text-rose-400" />
            </div>
            <div>
              <p className="font-semibold text-surface-900 dark:text-surface-100">Final PDF</p>
              <p className="text-sm text-surface-400 dark:text-surface-500">
                {hasValidPdf ? 'Download the generated report' : 'Report PDF not yet generated.'}
              </p>
            </div>
          </div>
          {hasValidPdf ? (
            <a
              href={report.final_pdf!}
              download
              className="btn-primary text-sm"
            >
              Download
            </a>
          ) : (
            <span className="text-sm text-surface-400 dark:text-surface-500 italic">Not generated</span>
          )}
        </div>
      </div>
    </div>
  )
}
