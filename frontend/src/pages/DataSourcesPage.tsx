import { useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Database, Search, CheckCircle, AlertTriangle, XCircle, Clock, HardDrive, Plus, X, ChevronLeft, ChevronRight } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import { useDataSources, useCreateDataSource } from '../hooks/useDataSources'
import { useProjects } from '../hooks/useProjects'
import type { DataSource } from '../types'

const statusIcons: Record<string, ReactNode> = {
  pending: <Clock className="h-3.5 w-3.5 text-amber-500" />,
  valid: <CheckCircle className="h-3.5 w-3.5 text-primary-500" />,
  flagged: <AlertTriangle className="h-3.5 w-3.5 text-orange-500" />,
  rejected: <XCircle className="h-3.5 w-3.5 text-red-500" />,
}

const statusBadge: Record<string, string> = {
  pending: 'badge-amber',
  valid: 'badge-green',
  flagged: 'bg-orange-50 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300',
  rejected: 'badge-red',
}

export default function DataSourcesPage() {
  const navigate = useNavigate()
  const [projectFilter, setProjectFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const { data: projects } = useProjects()
  const { data: sources, isLoading, isError, error } = useDataSources()
  const createDataSource = useCreateDataSource()
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})
  const [page, setPage] = useState(1)
  const perPage = 10

  const [form, setForm] = useState({
    project_id: '',
    source_type: 'mobile_survey' as DataSource['source_type'],
    schema_version: 'v1.0',
    validation_status: 'pending' as DataSource['validation_status'],
  })

  const validate = () => {
    const errors: Record<string, string> = {}
    if (!form.project_id) errors.project_id = 'Project is required'
    if (!form.schema_version) errors.schema_version = 'Schema version is required'
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    createDataSource.mutate({
      project_id: form.project_id,
      source_type: form.source_type,
      schema_version: form.schema_version,
      validation_status: form.validation_status,
    })
    setShowCreate(false)
    setForm({ project_id: '', source_type: 'mobile_survey', schema_version: 'v1.0', validation_status: 'pending' })
    setFormErrors({})
  }

  const filtered = sources?.filter((s) =>
    projectFilter ? s.project_id.includes(projectFilter) : true
  )

  useEffect(() => {
    setPage(1)
  }, [projectFilter])

  const paginated = filtered?.slice((page - 1) * perPage, page * perPage)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">Data Sources</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Monitor and manage all incoming MRV data sources
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
          <Plus className="w-4 h-4" />
          New Data Source
        </button>
      </div>

      {/* Filter */}
      <div className="relative max-w-md">
        <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
        <input
          type="text"
          placeholder="Filter by project ID..."
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="input-modern pl-10"
        />
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
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                    <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Source Type</th>
                    <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Schema</th>
                    <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Project</th>
                    <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                  {paginated?.map((source) => (
                    <tr key={source.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors cursor-pointer" onClick={() => navigate(`/data-sources/${source.id}`)}>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                            <Database className="w-4 h-4 text-surface-500 dark:text-surface-400" />
                          </div>
                          <span className="font-semibold text-surface-900 dark:text-surface-100 capitalize">
                            {(source.source_type || '').replace('_', ' ')}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-surface-600 dark:text-surface-300">{source.schema_version}</td>
                      <td className="px-6 py-4">
                        <span className={`badge inline-flex items-center gap-1.5 ${statusBadge[source.validation_status] || 'badge-slate'}`}>
                          {statusIcons[source.validation_status]}
                          {source.validation_status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-xs text-surface-500 dark:text-surface-400 bg-surface-100 dark:bg-surface-800 px-2 py-1 rounded-md">
                          {source.project_id.slice(0, 8)}...
                        </span>
                      </td>
                      <td className="px-6 py-4 text-surface-500 dark:text-surface-400">
                        {new Date(source.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                  {filtered?.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center">
                        <div className="flex flex-col items-center gap-3">
                          <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                            <HardDrive className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                          </div>
                          <div className="text-sm text-surface-500 dark:text-surface-400">No data sources found.</div>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          {filtered && filtered.length > 0 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-surface-500 dark:text-surface-400">
                Showing {(page - 1) * perPage + 1}-{Math.min(page * perPage, filtered.length)} of {filtered.length}
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
                  disabled={page * perPage >= filtered.length}
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
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Add Data Source</h3>
              <button onClick={() => setShowCreate(false)} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project <span className="text-red-500">*</span></label>
                <select
                  value={form.project_id}
                  onChange={(e) => { setForm({ ...form, project_id: e.target.value }); setFormErrors(prev => { const n = { ...prev }; delete n.project_id; return n }) }}
                  className={`input-modern appearance-none cursor-pointer ${formErrors.project_id ? 'border-red-500 dark:border-red-500 focus:ring-red-500' : ''}`}
                >
                  <option value="">Select a project</option>
                  {(projects || []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
                {formErrors.project_id && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{formErrors.project_id}</p>}
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Source Type</label>
                <select
                  value={form.source_type}
                  onChange={(e) => setForm({ ...form, source_type: e.target.value as DataSource['source_type'] })}
                  className="input-modern appearance-none cursor-pointer"
                >
                  <option value="satellite">Satellite</option>
                  <option value="iot">IoT</option>
                  <option value="mobile_survey">Mobile Survey</option>
                  <option value="document">Document</option>
                  <option value="manual_entry">Manual Entry</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Schema Version <span className="text-red-500">*</span></label>
                <input
                  value={form.schema_version}
                  onChange={(e) => { setForm({ ...form, schema_version: e.target.value }); setFormErrors(prev => { const n = { ...prev }; delete n.schema_version; return n }) }}
                  className={`input-modern ${formErrors.schema_version ? 'border-red-500 dark:border-red-500 focus:ring-red-500' : ''}`}
                />
                {formErrors.schema_version && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{formErrors.schema_version}</p>}
              </div>
              <div className="flex gap-2 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary flex-1 text-sm">Cancel</button>
                <button type="submit" disabled={Object.keys(formErrors).length > 0} className="btn-primary flex-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed">Add Data Source</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
