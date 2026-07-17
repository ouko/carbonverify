import type { GeneratedMethodology } from '../../types'

export function MethodologyDraftViewer({ gm }: { gm: GeneratedMethodology }) {
  const methodology = gm.methodology
  if (!methodology) return <p className="text-surface-500 dark:text-surface-400">No draft methodology yet.</p>
  return (
    <div className="space-y-4">
      {Object.entries(methodology).map(([key, value]) => (
        <div key={key} className="border border-surface-200 dark:border-surface-700 rounded-xl p-3 bg-white dark:bg-surface-900/50">
          <h4 className="font-semibold capitalize mb-1 text-surface-900 dark:text-surface-100">{key.replace(/_/g, ' ')}</h4>
          <div className="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">
            {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
          </div>
        </div>
      ))}
    </div>
  )
}
