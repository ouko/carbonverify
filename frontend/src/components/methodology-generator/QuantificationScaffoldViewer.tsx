import type { GeneratedMethodology } from '../../types'

interface QuantificationScaffoldShape {
  equations?: Record<string, unknown>
  parameters?: Array<{
    name?: string
    description?: string
    unit?: string
    data_source?: string
    uncertainty?: string
  }>
  monitoring_frequency?: string
}

export function QuantificationScaffoldViewer({ gm }: { gm: GeneratedMethodology }) {
  const scaffold = (gm.quantification_scaffold ?? null) as QuantificationScaffoldShape | null
  if (!scaffold) return <p className="text-surface-500 dark:text-surface-400">No quantification scaffold yet.</p>
  return (
    <div className="space-y-4 text-surface-700 dark:text-surface-300">
      {!!scaffold.equations && Object.keys(scaffold.equations).length > 0 && (
        <div>
          <h4 className="font-semibold text-surface-900 dark:text-surface-100">Equations</h4>
          <pre className="bg-surface-50 dark:bg-surface-900 p-3 rounded text-sm overflow-x-auto">{JSON.stringify(scaffold.equations, null, 2)}</pre>
        </div>
      )}
      {Array.isArray(scaffold.parameters) && (
        <div>
          <h4 className="font-semibold text-surface-900 dark:text-surface-100">Parameters</h4>
          <table className="min-w-full text-sm border border-surface-200 dark:border-surface-700">
            <thead className="bg-surface-100 dark:bg-surface-800">
              <tr>
                <th className="px-2 py-1 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-100">Name</th>
                <th className="px-2 py-1 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-100">Description</th>
                <th className="px-2 py-1 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-100">Unit</th>
                <th className="px-2 py-1 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-100">Data Source</th>
                <th className="px-2 py-1 border border-surface-200 dark:border-surface-700 text-surface-900 dark:text-surface-100">Uncertainty</th>
              </tr>
            </thead>
            <tbody>
              {scaffold.parameters.map((p, i) => (
                <tr key={i}>
                  <td className="px-2 py-1 border border-surface-200 dark:border-surface-700">{p.name}</td>
                  <td className="px-2 py-1 border border-surface-200 dark:border-surface-700">{p.description}</td>
                  <td className="px-2 py-1 border border-surface-200 dark:border-surface-700">{p.unit}</td>
                  <td className="px-2 py-1 border border-surface-200 dark:border-surface-700">{p.data_source}</td>
                  <td className="px-2 py-1 border border-surface-200 dark:border-surface-700">{p.uncertainty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {typeof scaffold.monitoring_frequency === 'string' && scaffold.monitoring_frequency.length > 0 && (
        <div>
          <strong className="text-surface-900 dark:text-surface-100">Monitoring frequency:</strong> {scaffold.monitoring_frequency}
        </div>
      )}
    </div>
  )
}
