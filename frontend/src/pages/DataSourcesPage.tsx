import { useState } from 'react'
import type { ReactNode } from 'react'
import { Database, CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { DataSource } from '../types'

const statusIcons: Record<string, ReactNode> = {
  pending: <Clock className="h-4 w-4 text-amber-500" />,
  valid: <CheckCircle className="h-4 w-4 text-green-500" />,
  flagged: <AlertTriangle className="h-4 w-4 text-orange-500" />,
  rejected: <XCircle className="h-4 w-4 text-red-500" />,
}

const statusBadge: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  valid: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  flagged: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

export default function DataSourcesPage() {
  const [projectFilter, setProjectFilter] = useState('')
  const { data: sources, isLoading } = useQuery<DataSource[]>({
    queryKey: ['data-sources'],
    queryFn: async () => {
      const res = await api.get('/data-sources/')
      return res.data
    },
  })

  const filtered = sources?.filter((s) =>
    projectFilter ? s.project_id.includes(projectFilter) : true
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="relative">
          <Database className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Filter by project ID..."
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm text-gray-900 focus:border-primary-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          />
        </div>
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
                <th className="px-6 py-3 font-medium">Source Type</th>
                <th className="px-6 py-3 font-medium">Schema Version</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Project ID</th>
                <th className="px-6 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {filtered?.map((source) => (
                <tr key={source.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-gray-100">
                    {source.source_type.replace('_', ' ')}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">{source.schema_version}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge[source.validation_status]}`}>
                      {statusIcons[source.validation_status]}
                      {source.validation_status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300 font-mono text-xs">
                    {source.project_id.slice(0, 8)}...
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                    {new Date(source.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {filtered?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                    No data sources found.
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
