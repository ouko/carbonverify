import { useState } from 'react'
import { Calculator, Filter, FileBarChart, Plus, X } from 'lucide-react'
import { useCalculations, useCreateCalculation } from '../hooks/useCalculations'
import { useProjects } from '../hooks/useProjects'
import type { CalculationRun } from '../types'

const statusBadge: Record<string, string> = {
  draft: 'badge-slate',
  review_pending: 'badge-amber',
  approved: 'badge-green',
  rejected: 'badge-red',
}

const statusOptions = [
  { value: 'all', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'review_pending', label: 'Review Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

export default function CalculationsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [showCreate, setShowCreate] = useState(false)
  const { data: projects } = useProjects()
  const { data: calculations, isLoading } = useCalculations()
  const createCalculation = useCreateCalculation()

  const [form, setForm] = useState({
    project_id: '',
    monitoring_period_start: '2024-01-01',
    monitoring_period_end: '2024-03-31',
    fNRB_value: 0.4,
    emissions_reduction_tCO2e: 10000,
    confidence_score: 0.85,
    status: 'draft' as CalculationRun['status'],
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createCalculation.mutate({
      project_id: form.project_id,
      monitoring_period_start: form.monitoring_period_start,
      monitoring_period_end: form.monitoring_period_end,
      fNRB_value: form.fNRB_value,
      emissions_reduction_tCO2e: form.emissions_reduction_tCO2e,
      status: form.status,
    })
    setShowCreate(false)
    setForm({ project_id: '', monitoring_period_start: '2024-01-01', monitoring_period_end: '2024-03-31', fNRB_value: 0.4, emissions_reduction_tCO2e: 10000, confidence_score: 0.85, status: 'draft' })
  }

  const filtered = calculations?.filter((c) =>
    statusFilter === 'all' ? true : c.status === statusFilter
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">Calculations</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Review and manage emissions reduction calculations
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
            <Plus className="w-4 h-4" />
            Run Calculation
          </button>
          <div className="relative">
            <Filter className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input-modern pl-10 pr-10 appearance-none cursor-pointer"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
              <svg className="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="relative">
            <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
          </div>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered?.map((calc) => (
            <div key={calc.id} className="card-hover p-5 group">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
                    <Calculator className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                  </div>
                  <span className="font-semibold text-surface-900 dark:text-surface-100">Calculation</span>
                </div>
                <span className={`badge ${statusBadge[calc.status] || 'badge-slate'}`}>
                  {(calc.status || '').replace('_', ' ')}
                </span>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-surface-400 dark:text-surface-500">Project</span>
                  <span className="font-mono text-xs text-surface-600 dark:text-surface-400 bg-surface-100 dark:bg-surface-800 px-2 py-0.5 rounded">
                    {calc.project_id.slice(0, 8)}...
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-400 dark:text-surface-500">Period</span>
                  <span className="text-surface-600 dark:text-surface-300 text-xs">
                    {calc.monitoring_period_start} → {calc.monitoring_period_end}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-400 dark:text-surface-500">Emissions Reduced</span>
                  <span className="font-semibold text-primary-600 dark:text-primary-400">
                    {calc.emissions_reduction_tCO2e?.toLocaleString() ?? 'N/A'} tCO2e
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-400 dark:text-surface-500">Confidence</span>
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-1.5 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                      <div className="h-full rounded-full bg-primary-500" style={{ width: `${Math.round((calc.confidence_score || 0) * 100)}%` }} />
                    </div>
                    <span className="text-xs text-surface-500 dark:text-surface-400 tabular-nums">
                      {Math.round((calc.confidence_score || 0) * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {filtered?.length === 0 && (
            <div className="col-span-full card p-12 text-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                  <FileBarChart className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                </div>
                <p className="text-sm text-surface-500 dark:text-surface-400">No calculations found.</p>
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
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Run New Calculation</h3>
              <button onClick={() => setShowCreate(false)} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project</label>
                <select value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} className="input-modern appearance-none cursor-pointer">
                  <option value="">Select a project</option>
                  {(projects || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Period Start</label>
                  <input type="date" value={form.monitoring_period_start} onChange={(e) => setForm({ ...form, monitoring_period_start: e.target.value })} className="input-modern" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Period End</label>
                  <input type="date" value={form.monitoring_period_end} onChange={(e) => setForm({ ...form, monitoring_period_end: e.target.value })} className="input-modern" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">fNRB Value</label>
                  <input type="number" step="0.01" value={form.fNRB_value} onChange={(e) => setForm({ ...form, fNRB_value: parseFloat(e.target.value) })} className="input-modern" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Emissions (tCO2e)</label>
                  <input type="number" value={form.emissions_reduction_tCO2e} onChange={(e) => setForm({ ...form, emissions_reduction_tCO2e: parseInt(e.target.value) })} className="input-modern" />
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1 text-sm">Cancel</button>
                <button type="submit" className="btn-primary flex-1 text-sm">Run Calculation</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
