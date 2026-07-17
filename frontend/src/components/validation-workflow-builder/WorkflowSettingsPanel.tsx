import { JsonEditor } from './JsonEditor'
import type { WorkflowGraph } from '../../types'

interface WorkflowSettingsPanelProps {
  name: string
  version: string
  description: string
  graph: WorkflowGraph
  onChangeName: (name: string) => void
  onChangeVersion: (version: string) => void
  onChangeDescription: (description: string) => void
  onChangeGraph: (graph: WorkflowGraph) => void
}

export function WorkflowSettingsPanel({
  name,
  version,
  description,
  graph,
  onChangeName,
  onChangeVersion,
  onChangeDescription,
  onChangeGraph,
}: WorkflowSettingsPanelProps) {
  return (
    <div className="p-4 space-y-4">
      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Workflow Settings</h3>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Name</label>
        <input value={name} onChange={(e) => onChangeName(e.target.value)} className="input-modern" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Version</label>
        <input value={version} onChange={(e) => onChangeVersion(e.target.value)} className="input-modern" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => onChangeDescription(e.target.value)}
          rows={3}
          className="input-modern"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Entry Step</label>
        <select
          value={graph.entry_step}
          onChange={(e) => onChangeGraph({ ...graph, entry_step: e.target.value })}
          className="input-modern w-full"
        >
          {graph.steps.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
          SLA Seconds (optional)
        </label>
        <input
          type="number"
          value={graph.sla_seconds || ''}
          onChange={(e) => onChangeGraph({ ...graph, sla_seconds: e.target.value ? Number(e.target.value) : undefined })}
          className="input-modern"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="human-gates"
          type="checkbox"
          checked={graph.human_gates_required}
          onChange={(e) => onChangeGraph({ ...graph, human_gates_required: e.target.checked })}
          className="rounded border-surface-300"
        />
        <label htmlFor="human-gates" className="text-sm text-surface-700 dark:text-surface-300">
          Require human approval at decision gates by default
        </label>
      </div>

      <JsonEditor
        label="Global Variables"
        value={graph.variables}
        onChange={(variables) => onChangeGraph({ ...graph, variables: variables as Record<string, unknown> })}
      />
    </div>
  )
}
