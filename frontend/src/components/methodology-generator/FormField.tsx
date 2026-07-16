import { ReactNode } from 'react'

interface FormFieldProps {
  label: string
  htmlFor?: string
  helper?: string
  error?: string
  advanced?: boolean
  children: ReactNode
}

export function FormField({ label, htmlFor, helper, error, advanced, children }: FormFieldProps) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <label
          htmlFor={htmlFor}
          className="block text-sm font-medium text-surface-700 dark:text-surface-300"
        >
          {label}
        </label>
        {advanced && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400">
            Advanced
          </span>
        )}
      </div>
      {children}
      {helper && !error && (
        <p className="mt-1 text-xs text-surface-500 dark:text-surface-400">{helper}</p>
      )}
      {error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
