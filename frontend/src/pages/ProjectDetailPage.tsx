import { useParams } from 'react-router-dom'
import { ArrowLeft, Database, Calculator, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useProject } from '../hooks/useProjects'

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading } = useProject(id || '')

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent" />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
        <p className="text-gray-500 dark:text-gray-400">Project not found.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Link
          to="/projects"
          className="inline-flex items-center rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{project.name}</h1>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Methodology</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{project.methodology}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{project.status.replace('_', ' ')}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Confidence Threshold</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{project.confidence_threshold}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Complexity Score</p>
          <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{project.complexity_score ?? 'N/A'}</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          to="/data-sources"
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-6 transition-colors hover:border-primary-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-primary-700"
        >
          <div className="rounded-lg bg-primary-50 p-3 dark:bg-primary-900/20">
            <Database className="h-6 w-6 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">Data Sources</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">View project data</p>
          </div>
        </Link>
        <Link
          to="/calculations"
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-6 transition-colors hover:border-primary-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-primary-700"
        >
          <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
            <Calculator className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">Calculations</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Review calculations</p>
          </div>
        </Link>
        <Link
          to="/reports"
          className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-6 transition-colors hover:border-primary-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-primary-700"
        >
          <div className="rounded-lg bg-amber-50 p-3 dark:bg-amber-900/20">
            <FileText className="h-6 w-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <p className="font-medium text-gray-900 dark:text-gray-100">Reports</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">Generate reports</p>
          </div>
        </Link>
      </div>
    </div>
  )
}
