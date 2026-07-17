import type { WorkflowGraph } from '../../types'

interface GraphPreviewProps {
  graph: WorkflowGraph
}

export function GraphPreview({ graph }: GraphPreviewProps) {
  const nodeHeight = 36
  const nodeGap = 56
  const width = 600
  const height = Math.max(120, graph.steps.length * (nodeHeight + nodeGap) + 40)
  const centerX = width / 2

  const nodeY = (index: number) => 30 + index * (nodeHeight + nodeGap)

  const stepIndex = new Map(graph.steps.map((s, i) => [s.id, i]))

  return (
    <div className="p-4 overflow-auto">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
        Graph Preview
      </h3>
      <svg width={width} height={height} className="bg-surface-50 dark:bg-surface-900/50 rounded-lg border border-surface-200 dark:border-surface-700">
        {graph.steps.map((step, index) => {
          const y = nodeY(index)
          return (
            <g key={step.id}>
              <rect
                x={centerX - 90}
                y={y}
                width={180}
                height={nodeHeight}
                rx={6}
                className={`${
                  step.id === graph.entry_step
                    ? 'fill-primary-100 stroke-primary-500 dark:fill-primary-950 dark:stroke-primary-500'
                    : 'fill-white stroke-surface-300 dark:fill-surface-800 dark:stroke-surface-600'
                }`}
                strokeWidth={step.id === graph.entry_step ? 2 : 1}
              />
              <text
                x={centerX}
                y={y + 22}
                textAnchor="middle"
                className="text-xs fill-surface-800 dark:fill-surface-200"
              >
                {step.id}
              </text>
            </g>
          )
        })}

        {graph.steps.map((step, index) => {
          const fromY = nodeY(index) + nodeHeight
          const targets = [...step.next_on_success, ...step.next_on_failure]
          return targets.map((targetId, tidx) => {
            const targetIndex = stepIndex.get(targetId)
            if (targetIndex === undefined) return null
            const toY = nodeY(targetIndex)
            const isFailure = tidx >= step.next_on_success.length
            return (
              <path
                key={`${step.id}-${targetId}-${tidx}`}
                d={`M ${centerX} ${fromY} L ${centerX} ${toY - 4}`}
                markerEnd="url(#arrow)"
                fill="none"
                className={isFailure ? 'stroke-red-400 stroke-dashed' : 'stroke-surface-400'}
                strokeWidth={1.5}
                strokeDasharray={isFailure ? '4 4' : undefined}
              />
            )
          })
        })}

        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" className="fill-surface-400" />
          </marker>
        </defs>
      </svg>
    </div>
  )
}
