import { useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts'
import { Bot, AlertTriangle, Zap } from 'lucide-react'
import LoadingSpinner from '../../components/LoadingSpinner'
import { useAgentPerformance } from '../../hooks/useCommandData'

export function AgentPerformancePage() {
  const { data: agents, isLoading, isError, error } = useAgentPerformance()
  const [selectedAgent, setSelectedAgent] = useState<any>(null)

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

  const agentList = agents || []

  const radarData = selectedAgent
    ? [
        { metric: 'Tasks', value: Math.min(selectedAgent.tasksCompleted / 50, 100) },
        { metric: 'Confidence', value: selectedAgent.avgConfidence * 100 },
        { metric: 'Reliability', value: 100 - selectedAgent.escalationRate * 5 },
        { metric: 'Accuracy', value: 100 - selectedAgent.errorRate * 10 },
        { metric: 'Speed', value: Math.max(0, 100 - selectedAgent.avgExecutionTimeMs / 50) },
      ]
    : []

  return (
    <div className="space-y-6">
      {/* Agent Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {agentList.map((agent: any) => (
          <div
            key={agent.name}
            onClick={() => setSelectedAgent(agent)}
            className={`cursor-pointer rounded-2xl border p-5 transition-all hover:shadow-soft ${
              selectedAgent?.name === agent.name ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10' : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
                  <Bot className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                </div>
                <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{agent.name}</span>
              </div>
              {agent.improvementSuggestion && (
                <span title="Improvement suggested"><AlertTriangle className="h-4 w-4 text-amber-500" /></span>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-surface-400 dark:text-surface-500">Tasks</p>
                <p className="font-semibold text-surface-900 dark:text-surface-100">{agent.tasksCompleted.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-surface-400 dark:text-surface-500">Avg Confidence</p>
                <p className={`font-semibold ${agent.avgConfidence < 0.85 ? 'text-red-600 dark:text-red-400' : 'text-surface-900 dark:text-surface-100'}`}>
                  {Math.round(agent.avgConfidence * 100)}%
                </p>
              </div>
              <div>
                <p className="text-surface-400 dark:text-surface-500">Escalation</p>
                <p className={`font-semibold ${agent.escalationRate > 10 ? 'text-red-600 dark:text-red-400' : 'text-surface-900 dark:text-surface-100'}`}>
                  {agent.escalationRate}%
                </p>
              </div>
              <div>
                <p className="text-surface-400 dark:text-surface-500">Error Rate</p>
                <p className={`font-semibold ${agent.errorRate > 3 ? 'text-red-600 dark:text-red-400' : 'text-surface-900 dark:text-surface-100'}`}>
                  {agent.errorRate}%
                </p>
              </div>
            </div>
            {agent.improvementSuggestion && (
              <div className="mt-3 rounded-xl bg-amber-50 dark:bg-amber-950/10 p-2.5 text-[10px] text-amber-800 dark:text-amber-300 flex items-start gap-1.5">
                <Zap className="h-3 w-3 shrink-0 mt-0.5" />
                {agent.improvementSuggestion}
              </div>
            )}
          </div>
        ))}
      </div>

      {selectedAgent && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Radar Chart */}
          <div className="card p-5">
            <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">{selectedAgent.name} — Capability Profile</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="currentColor" opacity={0.1} />
                  <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.6 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.4 }} />
                  <Radar name={selectedAgent.name} dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Trend Line */}
          <div className="card p-5">
            <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">7-Day Confidence Trend</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={selectedAgent.trend.map((v: number, i: number) => ({ day: `D${i + 1}`, confidence: v }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                  <XAxis dataKey="day" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[60, 100]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(v: number) => `${v}%`}
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
          </div>
        </div>
      )}

      {/* Comparison Bar Chart */}
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Agent Comparison — Key Metrics</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={agentList}>
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.5 }} interval={0} angle={-15} textAnchor="end" height={60} axisLine={false} tickLine={false} />
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
              <Legend />
              <Bar dataKey="tasksCompleted" name="Tasks Completed" fill="#6366f1" radius={[6, 6, 0, 0]} />
              <Bar dataKey="humanReviewsRequired" name="Human Reviews" fill="#f59e0b" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Escalation vs Error Rate */}
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Escalation Rate vs Error Rate</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={agentList} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
              <XAxis type="number" domain={[0, 20]} tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.5 }} width={120} axisLine={false} tickLine={false} />
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
              <Bar dataKey="escalationRate" name="Escalation %" fill="#ef4444" radius={[0, 6, 6, 0]} />
              <Bar dataKey="errorRate" name="Error %" fill="#f59e0b" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
