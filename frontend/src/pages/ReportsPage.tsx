import { FileText, Download, ExternalLink } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import type { Report } from '../types'

const statusBadge: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  human_review: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  submitted: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  vvb_approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
}

export default function ReportsPage() {
  const { data: reports, isLoading } = useQuery<Report[]>({
    queryKey: ['reports'],
    queryFn: async () => {
      const res = await api.get('/reports/')
      return res.data
    },
  })

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reports?.map((report) => (
            <div
              key={report.id}
              className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800"
            >
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                  <span className="font-medium text-gray-900 dark:text-gray-100">Report</span>
                </div>
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge[report.status]}`}>
                  {report.status.replace('_', ' ')}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Template</span>
                  <span className="text-gray-700 dark:text-gray-300">{report.template_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Project</span>
                  <span className="font-mono text-xs text-gray-700 dark:text-gray-300">{report.project_id.slice(0, 8)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Created</span>
                  <span className="text-gray-700 dark:text-gray-300">
                    {new Date(report.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              {report.final_pdf && (
                <div className="mt-4 flex gap-2">
                  <a
                    href={report.final_pdf}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex flex-1 items-center justify-center rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                  >
                    <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                    View
                  </a>
                  <a
                    href={report.final_pdf}
                    download
                    className="inline-flex flex-1 items-center justify-center rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600"
                  >
                    <Download className="mr-1.5 h-3.5 w-3.5" />
                    Download
                  </a>
                </div>
              )}
            </div>
          ))}
          {reports?.length === 0 && (
            <div className="col-span-full rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
              <p className="text-gray-500 dark:text-gray-400">No reports found.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
