import { Plus, GitBranch, Database, PhoneCall, Globe, Mail, Camera, BrainCircuit, Timer, Layers, Subtitles } from 'lucide-react'
import type { WorkflowStepType } from '../../types'
import { WORKFLOW_TEMPLATES } from '../../lib/validationWorkflowTemplates'

const STEP_TYPES: { type: WorkflowStepType; label: string; icon: React.ElementType }[] = [
  { type: 'http_request', label: 'HTTP Request', icon: Globe },
  { type: 'database_query', label: 'DB Query', icon: Database },
  { type: 'service_call', label: 'Service Call', icon: PhoneCall },
  { type: 'external_api', label: 'External API', icon: Globe },
  { type: 'notification', label: 'Notification', icon: Mail },
  { type: 'dom_capture', label: 'DOM Capture', icon: Camera },
  { type: 'decision_gate', label: 'Decision Gate', icon: GitBranch },
  { type: 'ai_evaluation', label: 'AI Evaluation', icon: BrainCircuit },
  { type: 'wait', label: 'Wait', icon: Timer },
  { type: 'parallel', label: 'Parallel', icon: Layers },
  { type: 'subflow', label: 'Subflow', icon: Subtitles },
]

interface StepPaletteProps {
  onAddStep: (type: WorkflowStepType) => void
  onLoadTemplate: (name: string) => void
}

export function StepPalette({ onAddStep, onLoadTemplate }: StepPaletteProps) {
  return (
    <div className="space-y-6 p-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
          Step Types
        </h3>
        <div className="grid grid-cols-1 gap-2">
          {STEP_TYPES.map(({ type, label, icon: Icon }) => (
            <button
              key={type}
              type="button"
              onClick={() => onAddStep(type)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 hover:border-primary-300 dark:hover:border-primary-700 transition-colors text-left"
            >
              <Icon className="w-4 h-4 text-surface-500 dark:text-surface-400" />
              <span className="text-sm text-surface-700 dark:text-surface-300">{label}</span>
              <Plus className="w-3 h-3 ml-auto text-surface-400" />
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
          Templates
        </h3>
        <div className="space-y-2">
          {WORKFLOW_TEMPLATES.map((template) => (
            <button
              key={template.name}
              type="button"
              onClick={() => onLoadTemplate(template.name)}
              className="w-full text-left px-3 py-2 rounded-lg border border-dashed border-surface-300 dark:border-surface-600 hover:border-primary-400 dark:hover:border-primary-600 transition-colors"
            >
              <p className="text-sm font-medium text-surface-800 dark:text-surface-200">{template.name}</p>
              <p className="text-xs text-surface-500 dark:text-surface-400">{template.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
