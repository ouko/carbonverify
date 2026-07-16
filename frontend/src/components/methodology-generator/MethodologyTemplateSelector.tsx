import type { MethodologyTemplate } from '../../types'

interface MethodologyTemplateSelectorProps {
  templates: MethodologyTemplate[]
  selectedId?: string
  onSelect: (template: MethodologyTemplate) => void
}

export function MethodologyTemplateSelector({
  templates,
  selectedId,
  onSelect,
}: MethodologyTemplateSelectorProps) {
  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
        Start from a template
      </label>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {templates.map((template) => (
          <button
            key={template.id}
            type="button"
            onClick={() => onSelect(template)}
            className={`text-left rounded-xl border p-4 transition-all ${
              selectedId === template.id
                ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10'
                : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 hover:border-primary-200 dark:hover:border-primary-800'
            }`}
          >
            <p className="font-semibold text-surface-900 dark:text-surface-100">{template.name}</p>
            <p className="text-xs text-surface-500 dark:text-surface-400 mt-1">
              {template.description}
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}
