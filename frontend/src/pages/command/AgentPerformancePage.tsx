import { useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts'
import { Bot, AlertTriangle } from 'lucide-react'
import { useAgentPerformance } from '../../hooks/useCommandData'

export function AgentPerformancePage() {
  const { data: agents, isLoading } = useAgentPerformance()
  const [selectedAgent, setSelectedAgent] = useState<any>(null)

  if (isLoading) return <div className="py-12 text-center text-gray-500">Loading agent performance...</div>

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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {agentList.map((agent: any) => (
          <div
            key={agent.name}
            onClick={() => setSelectedAgent(agent)}
            className={`cursor-pointer rounded-lg border p-4 transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800 ${
              selectedAgent?.name === agent.name ? 'border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20' : 'border-gray-200 bg-white'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-indigo-500" />
                <span className="text-sm font-semibold text-gray-900 dark:text-white">{agent.name}</span>
              </div>
              {agent.improvementSuggestion && (
                <span title="Improvement suggested"><AlertTriangle className="h-4 w-4 text-yellow-500" /></span>
              )}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <p className="text-gray-500 dark:text-gray-400">Tasks</p>
                <p className="font-semibold text-gray-900 dark:text-white">{agent.tasksCompleted.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-gray-500 dark:text-gray-400">Avg Confidence</p>
                <p className={`font-semibold ${agent.avgConfidence < 0.85 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
                  {Math.round(agent.avgConfidence * 100)}%
                </p>
              </div>
              <div>
                <p className="text-gray-500 dark:text-gray-400">Escalation Rate</p>
                <p className={`font-semibold ${agent.escalationRate > 10 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
                  {agent.escalationRate}%
                </p>
              </div>
              <div>
                <p className="text-gray-500 dark:text-gray-400">Error Rate</p>
                <p className={`font-semibold ${agent.errorRate > 3 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
                  {agent.errorRate}%
                </p>
              </div>
            </div>
            {agent.improvementSuggestion && (
              <div className="mt-2 rounded bg-yellow-50 p-2 text-[10px] text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                💡 {agent.improvementSuggestion}
              </div>
            )}
          </div>
        ))}
      </div>

      {selectedAgent && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* Radar Chart */}
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">{selectedAgent.name} — Capability Profile</h3>
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Radar name={selectedAgent.name} dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Trend Line */}
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">7-Day Confidence Trend</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={selectedAgent.trend.map((v: number, i: number) => ({ day: `D${i + 1}`, confidence: v }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                <YAxis domain={[60, 100]} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `${v}%`} />
                <Line type="monotone" dataKey="confidence" stroke="#6366f1" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Comparison Bar Chart */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Agent Comparison — Key Metrics</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={agentList}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="tasksCompleted" name="Tasks Completed" fill="#6366f1" radius={[4, 4, 0, 0]} />
            <Bar dataKey="humanReviewsRequired" name="Human Reviews" fill="#f59e0b" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Escalation vs Error Rate */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Escalation Rate vs Error Rate</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={agentList} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
            <XAxis type="number" domain={[0, 20]} tick={{ fontSize: 12 }} />
            <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={120} />
            <Tooltip />
            <Legend />
            <Bar dataKey="escalationRate" name="Escalation %" fill="#ef4444" radius={[0, 4, 4, 0]} />
            <Bar dataKey="errorRate" name="Error %" fill="#f59e0b" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
