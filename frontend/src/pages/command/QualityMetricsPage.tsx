import { useState } from 'react'
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Cell,
} from 'recharts'
import { TrendingUp, AlertTriangle, ThumbsUp, Ticket } from 'lucide-react'
import { useQualityMetrics } from '../../hooks/useCommandData'

export function QualityMetricsPage() {
  const { data, isLoading } = useQualityMetrics()
  const [calibrationAgent, setCalibrationAgent] = useState('all')

  if (isLoading) return <div className="py-12 text-center text-gray-500">Loading quality metrics...</div>

  const metrics = data || {
    accuracyOverTime: [],
    rejectionByVVB: [],
    rejectionByMethodology: [],
    npsTrend: [],
    supportVolume: [],
    calibrationData: [],
  }

  const filteredCalibration = calibrationAgent === 'all'
    ? metrics.calibrationData
    : metrics.calibrationData.filter((d: any) => d.agent === calibrationAgent)

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
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Calc Accuracy</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">94.2%</p>
          <p className="text-xs text-green-600">+1.3% vs last month</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-yellow-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Rejection Rate</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">8.4%</p>
          <p className="text-xs text-red-600">+0.5% vs last month</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <ThumbsUp className="h-5 w-5 text-blue-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">NPS Score</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">62</p>
          <p className="text-xs text-green-600">+4 vs last month</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <Ticket className="h-5 w-5 text-purple-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Support Tickets</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">34</p>
          <p className="text-xs text-green-600">-12 vs last month</p>
        </div>
      </div>

      {/* Accuracy Over Time */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Calculation Accuracy vs Manual Spot-Checks</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={metrics.accuracyOverTime}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis domain={[80, 100]} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="manual" name="Manual Spot-Check" stroke="#6366f1" strokeWidth={2} dot={{ r: 4 }} />
            <Line type="monotone" dataKey="automated" name="Automated" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Rejection by VVB */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Rejection Rate by Registry</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={metrics.rejectionByVVB}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" name="Rejections" radius={[4, 4, 0, 0]}>
                {metrics.rejectionByVVB.map((_: any, i: number) => (
                  <Cell key={i} fill={['#6366f1', '#8b5cf6', '#ec4899'][i % 3]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Rejection by Methodology */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Rejection Rate by Methodology</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={metrics.rejectionByMethodology}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" name="Rejections" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* NPS Trend */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Client NPS Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metrics.npsTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="nps" name="NPS" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Support Volume */}
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Support Ticket Volume</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={metrics.supportVolume}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="tickets" name="Tickets" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Confidence Calibration */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-white">Agent Confidence Calibration</h3>
          <select
            value={calibrationAgent}
            onChange={(e) => setCalibrationAgent(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          >
            {agents.map((a) => (
              <option key={a} value={a}>{a === 'all' ? 'All Agents' : a}</option>
            ))}
          </select>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
            <XAxis type="number" dataKey="confidence" name="Confidence" domain={[0.5, 1]} tick={{ fontSize: 12 }} label={{ value: 'Predicted Confidence', position: 'bottom', fontSize: 12 }} />
            <YAxis type="number" dataKey="accuracy" name="Accuracy" domain={[0.5, 1]} tick={{ fontSize: 12 }} label={{ value: 'Actual Accuracy', angle: -90, position: 'insideLeft', fontSize: 12 }} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
            <Legend />
            {calibrationAgent === 'all' ? (
              ['Ingestion', 'Validation', 'Calculation', 'Reporting'].map((agent) => (
                <Scatter
                  key={agent}
                  name={agent}
                  data={metrics.calibrationData.filter((d: any) => d.agent === agent)}
                  fill={agentColors[agent]}
                />
              ))
            ) : (
              <Scatter
                name={calibrationAgent}
                data={filteredCalibration}
                fill={agentColors[calibrationAgent] || '#6366f1'}
              />
            )}
            {/* Perfect calibration line */}
            <Line type="linear" dataKey="x" stroke="#9ca3af" strokeDasharray="5 5" dot={false} data={[{ x: 0.5, y: 0.5 }, { x: 1, y: 1 }]} />
          </ScatterChart>
        </ResponsiveContainer>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          Points on the diagonal line indicate perfect calibration. Points below the line indicate overconfidence.
        </p>
      </div>
    </div>
  )
}
