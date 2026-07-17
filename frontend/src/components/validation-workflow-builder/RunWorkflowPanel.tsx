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

export function RunWorkflowPanel({ workflow, onRunCreated }: RunWorkflowPanelProps) {
  const { data: projects } = useProjects()
  const trigger = useTriggerRun()
  const [projectId, setProjectId] = useState('')
  const [triggerEvent, setTriggerEvent] = useState('manual_test')
  const [inputData, setInputData] = useState<Record<string, unknown>>({})

  const handleRun = async () => {
    const run = await trigger.mutateAsync({
      workflow_id: workflow.id,
      project_id: projectId || undefined,
      trigger_event: triggerEvent,
      input_data: inputData,
    })
    onRunCreated(run)
  }

  return (
    <div className="p-4 space-y-4 border-t border-surface-200 dark:border-surface-700">
      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Test Run</h3>

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
