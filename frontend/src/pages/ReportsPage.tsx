import { useState } from 'react'
import { FileText, Download, ExternalLink, FileArchive, Plus, X } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { Report } from '../types'
import { mockReports, addReport, mockProjects, mockCalculations } from '../lib/mockData'

const statusBadge: Record<string, string> = {
  draft: 'badge-slate',
  human_review: 'badge-amber',
  approved: 'badge-green',
  submitted: 'badge-blue',
  vvb_approved: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  rejected: 'badge-red',
}

export default function ReportsPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({
    project_id: mockProjects[0]?.id || '',
    calculation_run_id: mockCalculations[0]?.id || '',
    template_type: 'GoldStandard_TPDDTEC' as Report['template_type'],
    status: 'draft' as Report['status'],
  })

  const { data: reports, isLoading } = useQuery<Report[]>({
    queryKey: ['reports'],
    queryFn: async () => mockReports,
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    addReport({
      project_id: form.project_id,
      calculation_run_id: form.calculation_run_id,
      template_type: form.template_type,
      draft_content: {},
      final_pdf: null,
      status: form.status,
      vvb_feedback: null,
    })
    qc.invalidateQueries({ queryKey: ['reports'] })
    setShowCreate(false)
    setForm({ project_id: mockProjects[0]?.id || '', calculation_run_id: mockCalculations[0]?.id || '', template_type: 'GoldStandard_TPDDTEC', status: 'draft' })
  }

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

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="relative">
            <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
          </div>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reports?.map((report) => (
            <div key={report.id} className="card-hover p-5 group">
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
              {report.final_pdf && (
                <div className="mt-5 flex gap-2 pt-4 border-t border-surface-100 dark:border-surface-800/50">
                  <a href={report.final_pdf} target="_blank" rel="noopener noreferrer" className="btn-ghost flex-1 justify-center text-xs">
                    <ExternalLink className="w-3.5 h-3.5" />
                    View
                  </a>
                  <a href={report.final_pdf} download className="btn-primary flex-1 text-xs">
                    <Download className="w-3.5 h-3.5" />
                    Download
                  </a>
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
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Generate Report</h3>
              <button onClick={() => setShowCreate(false)} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project</label>
                <select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="input-modern appearance-none cursor-pointer">
                  {mockProjects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Calculation Run</label>
                <select value={form.calculation_run_id} onChange={(e) => setForm({ ...form, calculation_run_id: e.target.value })} className="input-modern appearance-none cursor-pointer">
                  {mockCalculations.map((c) => (
                    <option key={c.id} value={c.id}>{c.id} — {c.emissions_reduction_tCO2e?.toLocaleString()} tCO2e</option>
                  ))}
                </select>
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
                <button type="submit" className="btn-primary flex-1 text-sm">Generate Report</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
