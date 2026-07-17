import { AlertTriangle, XCircle } from 'lucide-react'

export interface ValidationIssue {
  type: 'error' | 'warning'
  message: string
  stepId?: string
}

interface ValidationIssuesPanelProps {
  issues: ValidationIssue[]
}

export function ValidationIssuesPanel({ issues }: ValidationIssuesPanelProps) {
  if (issues.length === 0) return null
  const errors = issues.filter((i) => i.type === 'error')
  const warnings = issues.filter((i) => i.type === 'warning')

  return (
    <div className="card border-l-4 border-l-amber-500 p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-amber-500" />
        <h3 className="font-semibold text-sm text-surface-900 dark:text-surface-100">
          {errors.length} error{errors.length !== 1 ? 's' : ''}, {warnings.length} warning
          {warnings.length !== 1 ? 's' : ''}
        </h3>
      </div>
      <ul className="space-y-1">
        {issues.map((issue, idx) => (
          <li key={idx} className="flex items-start gap-2 text-xs">
            {issue.type === 'error' ? (
              <XCircle className="w-4 h-4 text-red-500 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className="text-surface-700 dark:text-surface-300">
              {issue.stepId ? `[${issue.stepId}] ` : ''}
              {issue.message}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
