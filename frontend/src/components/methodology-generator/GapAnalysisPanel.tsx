import type { GeneratedMethodology } from '../../types'

interface GapAnalysisShape {
  fits_existing_methodology?: boolean
  matching_methodologies?: Array<{ name?: string; reason?: string }>
  gaps?: string[]
  recommendation?: string
}

export function GapAnalysisPanel({ gm }: { gm: GeneratedMethodology }) {
  const analysis = (gm.gap_analysis ?? null) as GapAnalysisShape | null
  if (!analysis) return <p className="text-gray-500">No gap analysis yet.</p>
  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2">
        <span className="font-semibold">Fits existing methodology?</span>
        <span>{analysis.fits_existing_methodology ? 'Yes' : 'No'}</span>
      </div>
      {Array.isArray(analysis.matching_methodologies) && analysis.matching_methodologies.length > 0 && (
        <div>
          <h4 className="font-semibold">Potential matches</h4>
          <ul className="list-disc pl-5 text-sm">
            {analysis.matching_methodologies.map((m, i) => (
              <li key={i}>{m.name}: {m.reason}</li>
            ))}
          </ul>
        </div>
      )}
      {Array.isArray(analysis.gaps) && (
        <div>
          <h4 className="font-semibold">Gaps</h4>
          <ul className="list-disc pl-5 text-sm">
            {analysis.gaps.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}
      {typeof analysis.recommendation === 'string' && analysis.recommendation.length > 0 && (
        <div className="bg-blue-50 p-3 rounded text-sm">
          <strong>Recommendation:</strong> {analysis.recommendation}
        </div>
      )}
    </div>
  )
}
