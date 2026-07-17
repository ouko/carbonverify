import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useWorkflow, useValidationRuns } from '../hooks/useValidationWorkflows'
import { WorkflowRunDetail } from '../components/validation-workflow-builder/WorkflowRunDetail'
import LoadingSpinner from '../components/LoadingSpinner'

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    return axiosErr.response?.data?.detail || 'Failed to load workflow'
  }
  if (err instanceof Error) return err.message
  return 'Failed to load workflow'
}

export default function ValidationWorkflowRunsPage() {
  const { id, runId } = useParams<{ id: string; runId: string }>()
  const navigate = useNavigate()
  const { data: workflow, isLoading, isError, error } = useWorkflow(id)
  const { data: runs } = useValidationRuns(id)

  if (isLoading) return <LoadingSpinner fullscreen />

  if (isError || !workflow) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6">
        <div className="card max-w-md w-full p-6 space-y-4">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Workflow not found</h2>
          <p className="text-sm text-surface-600 dark:text-surface-400">{getErrorMessage(error)}</p>
          <button onClick={() => navigate('/validation-workflows')} className="btn-secondary flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" /> Back to workflows
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/validation-workflows')} className="btn-ghost p-2">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h1 className="page-title">Runs: {workflow.name}</h1>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        <div className="lg:col-span-1 overflow-y-auto border-r border-surface-200 dark:border-surface-700 pr-4">
          <h2 className="section-title mb-3">History</h2>
          <ul className="space-y-2">
            {runs?.map((run) => (
              <li
                key={run.id}
                onClick={() => navigate(`/validation-workflows/${id}/runs/${run.id}`)}
                className={`card p-3 cursor-pointer text-sm ${runId === run.id ? 'border-primary-400' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{run.trigger_event}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-800">{run.status}</span>
                </div>
                <p className="text-xs text-surface-500 mt-1">{run.created_at}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="lg:col-span-2 overflow-y-auto">
          {runId ? <WorkflowRunDetail runId={runId} /> : <p className="text-surface-500">Select a run to view details.</p>}
        </div>
      </div>
    </div>
  )
}
