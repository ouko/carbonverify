import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Leaf, Building2, Calendar, Activity } from 'lucide-react'
import { useCreateProject } from '../hooks/useProjects'

const methodologies = [
  { value: 'TPDDTEC_v4', label: 'TPDDTEC v4', desc: 'Tiered Performance/Distribution — Cookstoves' },
  { value: 'VM0050', label: 'VM0050', desc: 'Methodology for Methane Recovery' },
  { value: 'VMR0006', label: 'VMR0006', desc: 'Revised VMR for Renewable Energy' },
  { value: 'AMS-II.G', label: 'AMS-II.G', desc: 'Energy Efficiency — Supply Side' },
]

export default function ProjectCreatePage() {
  const navigate = useNavigate()
  const createProject = useCreateProject()
  const [form, setForm] = useState({
    name: '',
    developer_id: '',
    methodology: 'TPDDTEC_v4' as const,
    crediting_period_start: '',
    crediting_period_end: '',
    confidence_threshold: 0.85,
    complexity_score: null as number | null,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [apiError, setApiError] = useState('')

  const validate = () => {
    const e: Record<string, string> = {}
    if (!form.name.trim()) e.name = 'Project name is required'
    if (!form.developer_id.trim()) e.developer_id = 'Developer ID is required'
    if (!form.crediting_period_start) e.crediting_period_start = 'Start date is required'
    if (!form.crediting_period_end) e.crediting_period_end = 'End date is required'
    if (form.crediting_period_start && form.crediting_period_end && form.crediting_period_start >= form.crediting_period_end) {
      e.crediting_period_end = 'End date must be after start date'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setApiError('')
    createProject.mutate(form, {
      onSuccess: () => {
        navigate('/projects')
      },
      onError: (err: any) => {
        setApiError(err?.response?.data?.detail || err?.message || 'Failed to create project')
      },
    })
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/projects')} aria-label="Go back" className="btn-ghost p-2">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="page-title">New Project</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500">Create a new carbon credit verification project</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="card p-6 space-y-6">
        {/* Project Name */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
            Project Name
          </label>
          <div className="relative">
            <Leaf className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Kenya Clean Cookstoves — Nairobi"
              className={`input-modern pl-10 ${errors.name ? 'border-red-400 focus:border-red-400 focus:ring-red-400/30' : ''}`}
            />
          </div>
          {errors.name && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.name}</p>}
        </div>

        {/* Developer ID */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
            Developer ID
          </label>
          <div className="relative">
            <Building2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
            <input
              value={form.developer_id}
              onChange={(e) => setForm({ ...form, developer_id: e.target.value })}
              placeholder="e.g. dev-001"
              className={`input-modern pl-10 ${errors.developer_id ? 'border-red-400' : ''}`}
            />
          </div>
          {errors.developer_id && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.developer_id}</p>}
        </div>

        {/* Methodology */}
        <div>
          <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
            Methodology
          </label>
          <div className="grid gap-2 sm:grid-cols-2">
            {methodologies.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setForm({ ...form, methodology: m.value as typeof form.methodology })}
                className={`flex items-start gap-3 rounded-xl border p-4 text-left transition-all ${
                  form.methodology === m.value
                    ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10'
                    : 'border-surface-200 dark:border-surface-700 hover:bg-surface-50 dark:hover:bg-surface-800/50'
                }`}
              >
                <div className={`mt-0.5 h-4 w-4 rounded-full border-2 flex items-center justify-center ${
                  form.methodology === m.value ? 'border-primary-500' : 'border-surface-300 dark:border-surface-600'
                }`}>
                  {form.methodology === m.value && <div className="h-2 w-2 rounded-full bg-primary-500" />}
                </div>
                <div>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{m.label}</p>
                  <p className="text-xs text-surface-400 dark:text-surface-500">{m.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Crediting Period */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Crediting Period Start
            </label>
            <div className="relative">
              <Calendar className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
              <input
                type="date"
                value={form.crediting_period_start}
                onChange={(e) => setForm({ ...form, crediting_period_start: e.target.value })}
                className={`input-modern pl-10 ${errors.crediting_period_start ? 'border-red-400' : ''}`}
              />
            </div>
            {errors.crediting_period_start && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.crediting_period_start}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Crediting Period End
            </label>
            <div className="relative">
              <Calendar className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
              <input
                type="date"
                value={form.crediting_period_end}
                onChange={(e) => setForm({ ...form, crediting_period_end: e.target.value })}
                className={`input-modern pl-10 ${errors.crediting_period_end ? 'border-red-400' : ''}`}
              />
            </div>
            {errors.crediting_period_end && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{errors.crediting_period_end}</p>}
          </div>
        </div>

        {/* Confidence & Complexity */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Confidence Threshold
            </label>
            <div className="relative">
              <Activity className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={form.confidence_threshold}
                onChange={(e) => setForm({ ...form, confidence_threshold: parseFloat(e.target.value) })}
                className="input-modern pl-10"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Complexity Score (optional)
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="10"
              value={form.complexity_score ?? ''}
              onChange={(e) => setForm({ ...form, complexity_score: e.target.value ? parseFloat(e.target.value) : null })}
              className="input-modern"
              placeholder="1–10"
            />
          </div>
        </div>

        {apiError && (
          <div className="rounded-xl bg-red-50 dark:bg-red-950/20 p-4 text-sm text-red-700 dark:text-red-300">
            {apiError}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button type="button" onClick={() => navigate('/projects')} className="btn-secondary">
            Cancel
          </button>
          <button
            type="submit"
            disabled={createProject.isPending}
            className="btn-primary"
          >
            {createProject.isPending ? (
              <div className="h-5 w-5 rounded-full border-[2.5px] border-white/30 border-t-white animate-spin" />
            ) : (
              'Create Project'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
