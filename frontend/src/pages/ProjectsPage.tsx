import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search, Filter, FolderOpen } from 'lucide-react'
import { useProjects } from '../hooks/useProjects'
import type { ProjectStatus } from '../types'

const statusBadge: Record<ProjectStatus, string> = {
  onboarding: 'badge-slate',
  data_collection: 'badge-blue',
  calculation: 'badge-amber',
  review: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
  submitted: 'badge-green',
  verified: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  monitoring: 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/50 dark:text-cyan-300',
}

const statusOptions: { value: ProjectStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All Statuses' },
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'data_collection', label: 'Data Collection' },
  { value: 'calculation', label: 'Calculation' },
  { value: 'review', label: 'Review' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'verified', label: 'Verified' },
  { value: 'monitoring', label: 'Monitoring' },
]

export default function ProjectsPage() {
  const navigate = useNavigate()
  const { data: projects, isLoading, isError, error } = useProjects()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<ProjectStatus | 'all'>('all')

  const filtered = projects?.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || p.status === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">Projects</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Manage and track your carbon credit verification projects
          </p>
        </div>
        <button onClick={() => navigate('/projects/new')} className="btn-primary text-sm">
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-modern pl-10"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as ProjectStatus | 'all')}
            className="input-modern pl-10 pr-10 appearance-none cursor-pointer"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none">
            <svg className="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* Table */}
      {isError ? (
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
          <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
        </div>
      ) : isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="relative">
            <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
            <div className="absolute inset-0 h-10 w-10 rounded-full border-[3px] border-transparent border-b-primary-300/30 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
          </div>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Name</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Methodology</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Crediting Period</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {filtered?.map((project) => (
                  <tr
                    key={project.id}
                    className="group hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-semibold text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 transition-colors"
                      >
                        {project.name}
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-surface-600 dark:text-surface-300">
                      {project.methodology}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${statusBadge[project.status as ProjectStatus] || 'badge-slate'}`}>
                        {(project.status || 'unknown').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-surface-600 dark:text-surface-300">
                      <span className="text-surface-400 dark:text-surface-500">{project.crediting_period_start}</span>
                      <span className="mx-1.5 text-surface-300 dark:text-surface-600">→</span>
                      <span className="text-surface-400 dark:text-surface-500">{project.crediting_period_end}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary-500 transition-all"
                            style={{ width: `${Math.round((project.confidence_threshold || 0) * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-surface-500 dark:text-surface-400 tabular-nums">
                          {Math.round((project.confidence_threshold || 0) * 100)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
                {filtered?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                          <FolderOpen className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                        </div>
                        <div className="text-sm text-surface-500 dark:text-surface-400">
                          No projects found
                        </div>
                        <div className="text-xs text-surface-400 dark:text-surface-500">
                          Try adjusting your search or filter criteria
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
