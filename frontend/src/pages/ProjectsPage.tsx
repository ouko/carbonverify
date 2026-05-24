import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Search, Filter } from 'lucide-react'
import { useProjects } from '../hooks/useProjects'
import type { ProjectStatus } from '../types'

const statusBadge: Record<ProjectStatus, string> = {
  onboarding: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  data_collection: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  calculation: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  review: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  submitted: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  verified: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  monitoring: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300',
}

export default function ProjectsPage() {
  const { data: projects, isLoading } = useProjects()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<ProjectStatus | 'all'>('all')

  const filtered = projects?.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase())
    const matchesFilter = filter === 'all' || p.status === filter
    return matchesSearch && matchesFilter
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search projects..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm text-gray-900 focus:border-primary-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 sm:w-64"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as ProjectStatus | 'all')}
              className="rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-8 text-sm text-gray-900 focus:border-primary-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="all">All Statuses</option>
              <option value="onboarding">Onboarding</option>
              <option value="data_collection">Data Collection</option>
              <option value="calculation">Calculation</option>
              <option value="review">Review</option>
              <option value="submitted">Submitted</option>
              <option value="verified">Verified</option>
              <option value="monitoring">Monitoring</option>
            </select>
          </div>
        </div>
        <button className="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600">
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </button>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 dark:bg-gray-700/50 dark:text-gray-400">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Methodology</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Crediting Period</th>
                <th className="px-6 py-3 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {filtered?.map((project) => (
                <tr key={project.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <td className="px-6 py-4">
                    <Link
                      to={`/projects/${project.id}`}
                      className="font-medium text-primary-600 hover:underline dark:text-primary-400"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">{project.methodology}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge[project.status]}`}>
                      {project.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                    {project.crediting_period_start} → {project.crediting_period_end}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                    {project.confidence_threshold}
                  </td>
                </tr>
              ))}
              {filtered?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                    No projects found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
