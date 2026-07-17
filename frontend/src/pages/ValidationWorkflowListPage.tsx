import { useNavigate } from 'react-router-dom'
import { Plus, Copy, GitBranch } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import { useWorkflows, useCreateWorkflow } from '../hooks/useValidationWorkflows'
import { api } from '../services/api'
import type { ValidationWorkflow } from '../types'

export default function ValidationWorkflowListPage() {
  const navigate = useNavigate()
  const { data: workflows, isLoading } = useWorkflows()
  const createWorkflow = useCreateWorkflow()

  const handleClone = async (workflow: ValidationWorkflow) => {
    const res = await api.get(`/validation/workflows/${workflow.id}`)
    const full = res.data
    const cloned = await createWorkflow.mutateAsync({
      name: `${workflow.name} (copy)`,
      version: workflow.version,
      description: workflow.description,
      workflow_graph: full.workflow_graph,
    })
    navigate(`/validation-workflows/${cloned.id}/builder`)
  }

  if (isLoading) return <LoadingSpinner fullscreen />

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title">Workflow Builder</h1>
        <button onClick={() => navigate('/validation-workflows/new/builder')} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {workflows?.map((workflow) => (
          <div
            key={workflow.id}
            className="card card-hover p-4 cursor-pointer"
            onClick={() => navigate(`/validation-workflows/${workflow.id}/builder`)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-primary-500" />
                <h3 className="font-semibold text-surface-900 dark:text-surface-100">{workflow.name}</h3>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full ${
                  workflow.active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200'
                    : 'bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400'
                }`}
              >
                {workflow.active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-2 line-clamp-2">{workflow.description || 'No description'}</p>
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-surface-400">v{workflow.version}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleClone(workflow)
                }}
                className="btn-ghost text-xs flex items-center gap-1"
              >
                <Copy className="w-3 h-3" /> Clone
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
