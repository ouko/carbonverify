import { useState } from 'react'
import { Calculator } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { CalculationRun } from '../types'

const statusBadge: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  review_pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

export default function CalculationsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const { data: calculations, isLoading } = useQuery<CalculationRun[]>({
    queryKey: ['calculations'],
    queryFn: async () => {
      const res = await api.get('/calculations/')
      return res.data
    },
  })

  const filtered = calculations?.filter((c) =>
    statusFilter === 'all' ? true : c.status === statusFilter
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-900 focus:border-primary-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
        >
          <option value="all">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="review_pending">Review Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered?.map((calc) => (
            <div
              key={calc.id}
              className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800"
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Calculator className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Calculation</span>
                </div>
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge[calc.status]}`}>
                  {calc.status.replace('_', ' ')}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Project</span>
                  <span className="font-mono text-xs text-gray-700 dark:text-gray-300">{calc.project_id.slice(0, 8)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Period</span>
                  <span className="text-gray-700 dark:text-gray-300">
                    {calc.monitoring_period_start} → {calc.monitoring_period_end}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Emissions Reduced</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {calc.emissions_reduction_tCO2e?.toLocaleString() ?? 'N/A'} tCO2e
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Confidence</span>
                  <span className="text-gray-700 dark:text-gray-300">{calc.confidence_score ?? 'N/A'}</span>
                </div>
              </div>
            </div>
          ))}
          {filtered?.length === 0 && (
            <div className="col-span-full rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
              <p className="text-gray-500 dark:text-gray-400">No calculations found.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
