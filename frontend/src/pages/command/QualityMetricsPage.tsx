import { useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Cell,
} from 'recharts'
import { TrendingUp, AlertTriangle, ThumbsUp, Ticket } from 'lucide-react'
import LoadingSpinner from '../../components/LoadingSpinner'
import { useQualityMetrics } from '../../hooks/useValidation'

export function QualityMetricsPage() {
  const { data, isLoading, isError, error } = useQualityMetrics()
  const [calibrationAgent, setCalibrationAgent] = useState('all')

  if (isLoading) return (
    <LoadingSpinner />
  )

  if (isError) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load data</p>
        <p className="text-sm text-surface-500 mt-2">{(error as any)?.response?.data?.detail || (error as Error)?.message || 'Unknown error'}</p>
      </div>
    )
  }

  const metrics = {
    accuracyOverTime: [],
    rejectionByVVB: [],
    rejectionByMethodology: [],
    npsTrend: [],
    supportVolume: [],
    calibrationData: [],
    ...data,
  }

  const filteredCalibration = calibrationAgent === 'all'
    ? metrics.calibrationData
    : metrics.calibrationData.filter((d: { agent: string }) => d.agent === calibrationAgent)

  const agents = ['all', 'Ingestion', 'Validation', 'Calculation', 'Reporting']
  const agentColors: Record<string, string> = {
    Ingestion: '#6366f1',
    Validation: '#8b5cf6',
    Calculation: '#ec4899',
    Reporting: '#f59e0b',
  }

  return (
    <div className="space-y-6">
      {/* Top Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: 'Calc Accuracy', value: `${metrics.accuracy_percent ?? 0}%`, icon: TrendingUp, color: 'text-primary-500' },
          { label: 'Rejection Rate', value: `${metrics.rejection_rate_percent ?? 0}%`, icon: AlertTriangle, color: 'text-amber-500' },
          { label: 'NPS Score', value: `${metrics.nps_score ?? 0}`, icon: ThumbsUp, color: 'text-blue-500' },
          { label: 'Support Tickets', value: `${metrics.total_rejections ?? 0}`, icon: Ticket, color: 'text-violet-500' },
        ].map((stat) => (
          <div key={stat.label} className="card p-5">
            <div className="flex items-center gap-2 mb-2">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              <span className="text-xs text-surface-400 dark:text-surface-500">{stat.label}</span>
            </div>
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Accuracy Over Time */}
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Calculation Accuracy vs Manual Spot-Checks</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={metrics.accuracyOverTime}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
              <YAxis domain={[80, 100]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  border: 'none',
                  borderRadius: '12px',
                  padding: '12px 16px',
                  color: '#f8fafc',
                  fontSize: '13px',
                }}
              />
              <Legend />
              <Line type="monotone" dataKey="manual" name="Manual Spot-Check" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 4, strokeWidth: 0 }} />
              <Line type="monotone" dataKey="automated" name="Automated" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4, strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Rejection by VVB */}
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Rejection Rate by Registry</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.rejectionByVVB}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Bar dataKey="value" name="Rejections" radius={[8, 8, 0, 0]}>
                  {metrics.rejectionByVVB.map((_: any, i: number) => (
                    <Cell key={i} fill={['#6366f1', '#8b5cf6', '#ec4899'][i % 3]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Rejection by Methodology */}
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Rejection Rate by Methodology</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.rejectionByMethodology}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Bar dataKey="value" name="Rejections" fill="#f59e0b" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* NPS Trend */}
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Client NPS Trend</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics.npsTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Line type="monotone" dataKey="nps" name="NPS" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 4, strokeWidth: 0 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Support Volume */}
        <div className="card p-5">
          <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Support Ticket Volume</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics.supportVolume}>
                <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    border: 'none',
                    borderRadius: '12px',
                    padding: '12px 16px',
                    color: '#f8fafc',
                    fontSize: '13px',
                  }}
                />
                <Bar dataKey="tickets" name="Tickets" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Confidence Calibration */}
      <div className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Agent Confidence Calibration</h3>
          <select
            value={calibrationAgent}
            onChange={(e) => setCalibrationAgent(e.target.value)}
            className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer"
          >
            {agents.map((a) => (
              <option key={a} value={a}>{a === 'all' ? 'All Agents' : a}</option>
            ))}
          </select>
        </div>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
              <XAxis type="number" dataKey="confidence" name="Confidence" domain={[0.5, 1]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} label={{ value: 'Predicted Confidence', position: 'bottom', fontSize: 12, fill: 'currentColor', opacity: 0.5 }} />
              <YAxis type="number" dataKey="accuracy" name="Accuracy" domain={[0.5, 1]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} label={{ value: 'Actual Accuracy', angle: -90, position: 'insideLeft', fontSize: 12, fill: 'currentColor', opacity: 0.5 }} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.95)', border: 'none', borderRadius: '12px', padding: '12px 16px', color: '#f8fafc', fontSize: '13px' }} />
              <Legend />
              {calibrationAgent === 'all' ? (
                ['Ingestion', 'Validation', 'Calculation', 'Reporting'].map((agent) => (
                  <Scatter key={agent} name={agent} data={metrics.calibrationData.filter((d: any) => d.agent === agent)} fill={agentColors[agent]} />
                ))
              ) : (
                <Scatter name={calibrationAgent} data={filteredCalibration} fill={agentColors[calibrationAgent] || '#6366f1'} />
              )}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-surface-400 dark:text-surface-500">
          Points on the diagonal line indicate perfect calibration. Points below the line indicate overconfidence.
        </p>
      </div>
    </div>
  )
}
