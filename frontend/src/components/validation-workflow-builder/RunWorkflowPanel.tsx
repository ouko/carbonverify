import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { JsonEditor } from './JsonEditor'
import { useProjects } from '../../hooks/useProjects'
import { useTriggerRun } from '../../hooks/useValidationWorkflows'
import type { ValidationWorkflow, ValidationRun } from '../../types'

interface RunWorkflowPanelProps {
  workflow: ValidationWorkflow
  onRunCreated: (run: ValidationRun) => void
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    return axiosErr.response?.data?.detail || 'An unexpected error occurred'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export function RunWorkflowPanel({ workflow, onRunCreated }: RunWorkflowPanelProps) {
  const { data: projects } = useProjects()
  const trigger = useTriggerRun()
  const [projectId, setProjectId] = useState('')
  const [triggerEvent, setTriggerEvent] = useState('manual_test')
  const [inputData, setInputData] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    setError(null)
    try {
      const run = await trigger.mutateAsync({
        workflow_id: workflow.id,
        project_id: projectId || undefined,
        trigger_event: triggerEvent,
        input_data: inputData,
      })
      onRunCreated(run)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="p-4 space-y-4 border-t border-surface-200 dark:border-surface-700">
      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Test Run</h3>
      {error && <div className="card border-l-4 border-l-red-500 p-3 text-sm text-red-700 dark:text-red-300">{error}</div>}

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Project (optional)</label>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input-modern w-full">
          <option value="">— None —</option>
          {projects?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Trigger event</label>
        <input value={triggerEvent} onChange={(e) => setTriggerEvent(e.target.value)} className="input-modern" />
      </div>

      <JsonEditor label="Input data" value={inputData} onChange={(value) => setInputData(value as Record<string, unknown>)} />

      <button
        type="button"
        onClick={handleRun}
        disabled={trigger.isPending}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {trigger.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
        Run workflow
      </button>
    </div>
  )
}
