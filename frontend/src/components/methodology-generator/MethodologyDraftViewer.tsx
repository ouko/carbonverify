import type { GeneratedMethodology } from '../../types'

export function MethodologyDraftViewer({ gm }: { gm: GeneratedMethodology }) {
  const methodology = gm.methodology
  if (!methodology) return <p className="text-gray-500">No draft methodology yet.</p>
  return (
    <div className="space-y-4">
      {Object.entries(methodology).map(([key, value]) => (
        <div key={key} className="border rounded p-3">
          <h4 className="font-semibold capitalize mb-1">{key.replace(/_/g, ' ')}</h4>
          <div className="text-sm text-gray-700 whitespace-pre-wrap">
            {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
          </div>
        </div>
      ))}
    </div>
  )
}
