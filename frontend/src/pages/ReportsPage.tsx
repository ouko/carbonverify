import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Download, FileArchive, Plus, X, ChevronLeft, ChevronRight } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import { useReports, useCreateReport } from '../hooks/useReports'
import { useProjects } from '../hooks/useProjects'
import { useCalculations } from '../hooks/useCalculations'
import type { Report } from '../types'

const statusBadge: Record<string, string> = {
  draft: 'badge-slate',
  human_review: 'badge-amber',
  approved: 'badge-green',
  submitted: 'badge-blue',
  vvb_approved: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  rejected: 'badge-red',
}

export default function ReportsPage() {
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const { data: projects } = useProjects()
  const { data: calculations } = useCalculations()
  const { data: reports, isLoading, isError, error } = useReports()
  const createReport = useCreateReport()
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)
  const perPage = 9

  const [form, setForm] = useState({
    project_id: '',
    calculation_run_id: '',
    template_type: 'GoldStandard_TPDDTEC' as Report['template_type'],
    status: 'draft' as Report['status'],
  })

  const validate = () => {
    const errors: Record<string, string> = {}
    if (!form.project_id) errors.project_id = 'Project is required'
    if (!form.calculation_run_id) errors.calculation_run_id = 'Calculation run is required'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    createReport.mutate({
      project_id: form.project_id,
      calculation_run_id: form.calculation_run_id,
      template_type: form.template_type,
      draft_content: {},
      status: form.status,
    })
    setShowCreate(false)
    setForm({ project_id: '', calculation_run_id: '', template_type: 'GoldStandard_TPDDTEC', status: 'draft' })
    setFormErrors({})
  }

  const paginated = reports?.slice((page - 1) * perPage, page * perPage)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">Reports</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Generate and manage VVB verification reports
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
          <Plus className="w-4 h-4" />
          Generate Report
        </button>
      </div>

      {isError ? (
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
          <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
        </div>
      ) : isLoading ? (
        <LoadingSpinner />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {paginated?.map((report) => (
              <div key={report.id} className="card-hover p-5 group cursor-pointer" onClick={() => navigate(`/reports/${report.id}`)}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <span className="font-semibold text-surface-900 dark:text-surface-100">Report</span>
                  </div>
                  <span className={`badge ${statusBadge[report.status] || 'badge-slate'}`}>
                    {(report.status || '').replace('_', ' ')}
                  </span>
                </div>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-surface-400 dark:text-surface-500">Template</span>
                    <span className="text-surface-600 dark:text-surface-300 capitalize">{(report.template_type || '').replace('_', ' ')}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-surface-400 dark:text-surface-500">Project</span>
                    <span className="font-mono text-xs text-surface-600 dark:text-surface-400 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">
                      {report.project_id.slice(0, 8)}...
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-surface-400 dark:text-surface-500">Created</span>
                    <span className="text-surface-600 dark:text-surface-300">
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                {report.final_pdf && !report.final_pdf.includes('example.com') ? (
                  <div className="mt-5 flex gap-2 pt-4 border-t border-surface-100 dark:border-surface-800/50">
                    <a href={report.final_pdf} download className="btn-primary flex-1 text-xs" onClick={(e) => e.stopPropagation()}>
                      <Download className="w-3.5 h-3.5" />
                      Download
                    </a>
                  </div>
                ) : (
                  <div className="mt-5 flex gap-2 pt-4 border-t border-surface-100 dark:border-surface-800/50">
                    <span className="text-xs text-surface-400 dark:text-surface-500 italic flex-1 text-center">Not generated</span>
                  </div>
                )}
              </div>
            ))}
            {reports?.length === 0 && (
              <div className="col-span-full card p-12 text-center">
                <div className="flex flex-col items-center gap-3">
                  <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                    <FileArchive className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                  </div>
                  <p className="text-sm text-surface-500 dark:text-surface-400">No reports found.</p>
                </div>
              </div>
            )}
          </div>
          {reports && reports.length > 0 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Showing {(page - 1) * perPage + 1}-{Math.min(page * perPage, reports.length)} of {reports.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Prev
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page * perPage >= reports.length}
                  className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Generate Report</h3>
              <button onClick={() => setShowCreate(false)} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project <span className="text-red-500">*</span></label>
                <select value={form.project_id} onChange={(e) => { setForm({ ...form, project_id: e.target.value }); setFormErrors(prev => { const n = { ...prev }; delete n.project_id; return n }) }} className={`input-modern appearance-none cursor-pointer ${formErrors.project_id ? 'border-red-500 dark:border-red-500 focus:ring-red-500' : ''}`}>
                  <option value="">Select a project</option>
                  {(projects || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                {formErrors.project_id && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{formErrors.project_id}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Calculation Run <span className="text-red-500">*</span></label>
                <select value={form.calculation_run_id} onChange={(e) => { setForm({ ...form, calculation_run_id: e.target.value }); setFormErrors(prev => { const n = { ...prev }; delete n.calculation_run_id; return n }) }} className={`input-modern appearance-none cursor-pointer ${formErrors.calculation_run_id ? 'border-red-500 dark:border-red-500 focus:ring-red-500' : ''}`}>
                  <option value="">Select a calculation</option>
                  {(calculations || []).map((c) => (
                    <option key={c.id} value={c.id}>{c.id} — {c.emissions_reduction_tCO2e?.toLocaleString()} tCO2e</option>
                  ))}
                </select>
                {formErrors.calculation_run_id && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{formErrors.calculation_run_id}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Template</label>
                <select value={form.template_type} onChange={(e) => setForm({ ...form, template_type: e.target.value as Report['template_type'] })} className="input-modern appearance-none cursor-pointer">
                  <option value="GoldStandard_TPDDTEC">Gold Standard TPDDTEC</option>
                  <option value="Verra_VM0050">Verra VM0050</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1 text-sm">Cancel</button>
                <button type="submit" disabled={Object.keys(formErrors).length > 0} className="btn-primary flex-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed">Generate Report</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
