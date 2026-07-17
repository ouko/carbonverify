import { Trash2, GripVertical } from 'lucide-react'
import type { WorkflowStep } from '../../types'

interface StepListProps {
  steps: WorkflowStep[]
  selectedId: string | null
  entryStep: string
  onSelect: (id: string) => void
  onRemove: (id: string) => void
  onMove: (fromIndex: number, toIndex: number) => void
}

export function StepList({ steps, selectedId, entryStep, onSelect, onRemove, onMove }: StepListProps) {
  return (
    <div className="space-y-2 p-4">
      {steps.map((step, index) => (
        <div
          key={step.id}
          onClick={() => onSelect(step.id)}
          className={`group flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
            selectedId === step.id
              ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10'
              : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 hover:border-primary-200 dark:hover:border-primary-800'
          }`}
        >
          <button
            type="button"
            className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 cursor-grab"
            onClick={(e) => {
              e.stopPropagation()
              if (index > 0) onMove(index, index - 1)
            }}
            aria-label="Move up"
          >
            <GripVertical className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-surface-500 dark:text-surface-400">{step.id}</span>
              {step.id === entryStep && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200">
                  entry
                </span>
              )}
              {!step.enabled && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400">
                  disabled
                </span>
              )}
            </div>
            <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">{step.name}</p>
            <p className="text-xs text-surface-500 dark:text-surface-400">{step.type}</p>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onRemove(step.id)
            }}
            className="opacity-0 group-hover:opacity-100 text-surface-400 hover:text-red-500 transition-opacity"
            aria-label="Remove step"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      {steps.length === 0 && (
        <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">
          No steps yet. Add one from the palette.
        </p>
      )}
    </div>
  )
}
