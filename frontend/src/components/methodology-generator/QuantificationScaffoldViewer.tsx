import type { GeneratedMethodology } from '../../types'

export function QuantificationScaffoldViewer({ gm }: { gm: GeneratedMethodology }) {
  const scaffold = gm.quantification_scaffold
  if (!scaffold) return <p className="text-gray-500">No quantification scaffold yet.</p>
  return (
    <div className="space-y-4">
      {scaffold.equations && (
        <div>
          <h4 className="font-semibold">Equations</h4>
          <pre className="bg-gray-50 p-3 rounded text-sm overflow-x-auto">{JSON.stringify(scaffold.equations, null, 2)}</pre>
        </div>
      )}
      {Array.isArray(scaffold.parameters) && (
        <div>
          <h4 className="font-semibold">Parameters</h4>
          <table className="min-w-full text-sm border">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-2 py-1 border">Name</th>
                <th className="px-2 py-1 border">Description</th>
                <th className="px-2 py-1 border">Unit</th>
                <th className="px-2 py-1 border">Data Source</th>
                <th className="px-2 py-1 border">Uncertainty</th>
              </tr>
            </thead>
            <tbody>
              {scaffold.parameters.map((p: any, i: number) => (
                <tr key={i}>
                  <td className="px-2 py-1 border">{p.name}</td>
                  <td className="px-2 py-1 border">{p.description}</td>
                  <td className="px-2 py-1 border">{p.unit}</td>
                  <td className="px-2 py-1 border">{p.data_source}</td>
                  <td className="px-2 py-1 border">{p.uncertainty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {scaffold.monitoring_frequency && (
        <div>
          <strong>Monitoring frequency:</strong> {scaffold.monitoring_frequency}
        </div>
      )}
    </div>
  )
}
