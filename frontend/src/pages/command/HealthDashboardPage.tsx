import {
  Activity, ShieldAlert, Bot, Inbox, Wrench, CheckCircle, AlertTriangle,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { useHealthScore, useDecisionConfidenceTrend } from '../../hooks/useHealthScore'

function scoreColor(score: number) {
  if (score >= 90) return '#10b981'
  if (score >= 70) return '#f59e0b'
  return '#ef4444'
}

function scoreTextClass(score: number) {
  if (score >= 90) return 'text-emerald-600 dark:text-emerald-400'
  if (score >= 70) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

/** Extract a human-readable message from an Axios/React Query error without swallowing it. */
function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || (error as Error)?.message || 'Unknown error'
}

function ScoreGauge({ score }: { score: number }) {
  // Semi-circular arc: 180° sweep, score mapped 0-100 onto the arc
  const radius = 70
  const cx = 90
  const cy = 85
  const clamped = Math.max(0, Math.min(100, score))
  const angle = (clamped / 100) * 180
  const rad = (Math.PI * (180 - angle)) / 180
  const endX = cx + radius * Math.cos(rad)
  const endY = cy - radius * Math.sin(rad)
  const largeArc = angle > 180 ? 1 : 0

  return (
    <svg viewBox="0 0 180 100" className="w-full max-w-xs mx-auto" role="img" aria-label={`Health score ${score}`}>
      <path
        d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
        fill="none"
        stroke="currentColor"
        strokeWidth="12"
        strokeLinecap="round"
        className="text-surface-200 dark:text-surface-700"
      />
      <path
        d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY}`}
        fill="none"
        stroke={scoreColor(score)}
        strokeWidth="12"
        strokeLinecap="round"
      />
      <text
        x={cx}
        y={cy - 12}
        textAnchor="middle"
        className="fill-surface-900 dark:fill-surface-100"
        style={{ fontSize: 28, fontWeight: 700 }}
      >
        {score}
      </text>
      <text
        x={cx}
        y={cy + 4}
        textAnchor="middle"
        className="fill-surface-400"
        style={{ fontSize: 10 }}
      >
        / 100
      </text>
    </svg>
  )
}

interface ComponentCardProps {
  title: string
  icon: React.ReactNode
  score?: number
  detail?: string
}

function ComponentCard({ title, icon, score, detail }: ComponentCardProps) {
  const configured = score !== undefined
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center text-surface-500 dark:text-surface-400">
            {icon}
          </div>
          <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{title}</span>
        </div>
        {configured && (
          <span className={`text-lg font-bold ${scoreTextClass(score)}`}>{Math.round(score)}</span>
        )}
      </div>
      {configured ? (
        <>
          <div className="mt-1 h-2 w-full rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
            <div
              className="h-2 rounded-full"
              style={{ width: `${Math.max(0, Math.min(100, score))}%`, backgroundColor: scoreColor(score) }}
            />
          </div>
          {detail && <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">{detail}</p>}
        </>
      ) : (
        <>
          <span className="badge badge-slate text-[10px]">not configured</span>
          <p className="mt-2 text-xs text-surface-400 dark:text-surface-500">
            Waiting for first data — this signal has not reported yet.
          </p>
        </>
      )}
    </div>
  )
}

export function HealthDashboardPage() {
  const { data: health, isLoading, isError, error } = useHealthScore()
  const { data: trend, isError: trendError } = useDecisionConfidenceTrend()

  if (isLoading) {
    return <div className="card p-8 text-center text-surface-400">Loading...</div>
  }
  if (isError || !health) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
        <p className="text-sm text-surface-500 mt-2">{isError ? errorMessage(error) : 'Unknown error'}</p>
      </div>
    )
  }

  const { components } = health
  const agentConfidence = components.agent_confidence
  const openEsc = components.open_escalations
  const queueDepth = components.review_queue_depth
  const remediation = components.remediation_resolution_rate
  const validation = components.validation_health
  const trendData = trend || []

  return (
    <div className="space-y-6">
      {/* Score gauge */}
      <div className="card p-6">
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-surface-400" />
            <h2 className="text-sm font-semibold text-surface-900 dark:text-surface-100">System Health</h2>
          </div>
          <ScoreGauge score={health.score} />
          <p className={`text-xs font-medium ${scoreTextClass(health.score)}`}>
            {health.score >= 90 ? 'Healthy' : health.score >= 70 ? 'Degraded' : 'Critical'}
          </p>
        </div>
      </div>

      {/* Component breakdown */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <ComponentCard
          title="Agent Confidence (24h)"
          icon={<Bot className="h-5 w-5" />}
          score={agentConfidence}
          detail={agentConfidence !== undefined ? 'Average orchestration decision confidence over the last 24 hours' : undefined}
        />
        <ComponentCard
          title="Open Escalations"
          icon={<ShieldAlert className="h-5 w-5" />}
          score={openEsc?.score}
          detail={openEsc ? `P0: ${openEsc.open_p0} · P1: ${openEsc.open_p1} · P2: ${openEsc.open_p2} open` : undefined}
        />
        <ComponentCard
          title="Review Queue Depth"
          icon={<Inbox className="h-5 w-5" />}
          score={queueDepth?.score}
          detail={queueDepth ? `${queueDepth.pending} pending / in review` : undefined}
        />
        <ComponentCard
          title="Remediation Resolution (7d)"
          icon={<Wrench className="h-5 w-5" />}
          score={remediation?.score}
          detail={remediation ? `${remediation.resolved} resolved · ${remediation.unresolved} unresolved` : undefined}
        />
        <ComponentCard
          title="Validation Health (7d)"
          icon={validation && validation.score >= 70 ? <CheckCircle className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
          score={validation?.score}
          detail={validation ? `${validation.completed} completed · ${validation.failed} failed` : undefined}
        />
      </div>

      {/* Agent confidence trend */}
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Agent Confidence Trend (auto-advance decisions)</h3>
        {trendError ? (
          <p className="py-8 text-center text-sm text-red-600 dark:text-red-400">Failed to load confidence trend</p>
        ) : trendData.length === 0 ? (
          <p className="py-8 text-center text-sm text-surface-400">No auto-advance decisions recorded yet</p>
        ) : (
          <div className="h-64" role="img" aria-label="Line chart of daily average agent confidence for auto-advance decisions">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(v: number) => [`${v}%`, 'Confidence']}
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Line type="monotone" dataKey="confidence" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 4, fill: '#6366f1', strokeWidth: 0 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
