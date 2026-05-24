import { useState } from 'react'
import { Search, Shield, CheckCircle, XCircle, ExternalLink } from 'lucide-react'

const MOCK_AUDIT_LOGS = [
  { id: '1', action: 'calculation_run', actor: 'CalculationAgent', actor_type: 'agent', target: 'Project 42', target_type: 'project', timestamp: '2024-06-15T10:30:00Z', input_hash: 'a1b2...', output_hash: 'c3d4...', radix_tx_ref: 'tx-sim-abc123', anchored: true },
  { id: '2', action: 'report_approved', actor: 'John Operator', actor_type: 'user', target: 'Report R-2024-06', target_type: 'report', timestamp: '2024-06-15T11:00:00Z', input_hash: null, output_hash: 'e5f6...', radix_tx_ref: 'tx-sim-def456', anchored: true },
  { id: '3', action: 'data_ingested', actor: 'IngestionAgent', actor_type: 'agent', target: 'File upload #128', target_type: 'data_source', timestamp: '2024-06-15T09:15:00Z', input_hash: 'g7h8...', output_hash: 'i9j0...', radix_tx_ref: null, anchored: false },
  { id: '4', action: 'human_reviewed', actor: 'Sarah Admin', actor_type: 'user', target: 'Queue item #45', target_type: 'review_queue', timestamp: '2024-06-14T16:45:00Z', input_hash: null, output_hash: null, radix_tx_ref: null, anchored: false },
  { id: '5', action: 'user_login', actor: 'john@carbonverify.io', actor_type: 'user', target: 'Account', target_type: 'user', timestamp: '2024-06-15T08:00:00Z', input_hash: null, output_hash: null, radix_tx_ref: null, anchored: false, mfa_used: true },
  { id: '6', action: 'breach_reported', actor: 'Security System', actor_type: 'system', target: 'Breach #3', target_type: 'breach', timestamp: '2024-06-14T22:00:00Z', input_hash: null, output_hash: null, radix_tx_ref: null, anchored: false },
]

const ACTION_COLORS: Record<string, string> = {
  calculation_run: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  report_approved: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  data_ingested: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  human_reviewed: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  user_login: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  breach_reported: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  methodology_updated: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300',
}

export function AuditLogPage() {
  const [search, setSearch] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [selectedLog, setSelectedLog] = useState<any>(null)
  const [verifying, setVerifying] = useState<string | null>(null)

  const filtered = MOCK_AUDIT_LOGS.filter((log) => {
    const matchesSearch = !search || log.target.toLowerCase().includes(search.toLowerCase()) || log.actor.toLowerCase().includes(search.toLowerCase())
    const matchesAction = !filterAction || log.action === filterAction
    return matchesSearch && matchesAction
  })

  const handleVerify = async (logId: string) => {
    setVerifying(logId)
    // Simulate verification
    await new Promise((r) => setTimeout(r, 1000))
    setVerifying(null)
  }

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-600" /> Audit Trail
        </h1>
        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1">
            <CheckCircle className="h-4 w-4 text-green-500" /> {MOCK_AUDIT_LOGS.filter(l => l.anchored).length} anchored
          </span>
          <span className="flex items-center gap-1">
            <XCircle className="h-4 w-4 text-gray-400" /> {MOCK_AUDIT_LOGS.filter(l => !l.anchored).length} unanchored
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by actor or target..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>
        <select
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
        >
          <option value="">All actions</option>
          <option value="calculation_run">Calculation Run</option>
          <option value="report_approved">Report Approved</option>
          <option value="data_ingested">Data Ingested</option>
          <option value="human_reviewed">Human Reviewed</option>
          <option value="user_login">User Login</option>
          <option value="breach_reported">Breach Reported</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="w-full text-left text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Action</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Actor</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Target</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Time</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Hash</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Radix</th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {filtered.map((log) => (
              <tr
                key={log.id}
                onClick={() => setSelectedLog(log)}
                className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <td className="px-4 py-3">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-800'}`}>
                    {log.action}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{log.actor}</td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{log.target}</td>
                <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500 dark:text-gray-400">
                  {log.output_hash || log.input_hash || '—'}
                </td>
                <td className="px-4 py-3">
                  {log.anchored ? (
                    <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                      <CheckCircle className="h-3.5 w-3.5" /> {log.radix_tx_ref?.slice(0, 12)}...
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {log.anchored && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleVerify(log.id) }}
                      className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
                    >
                      {verifying === log.id ? 'Verifying...' : 'Verify'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail Panel */}
      {selectedLog && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 dark:text-white">Audit Entry Details</h3>
            <button onClick={() => setSelectedLog(null)} className="text-gray-400 hover:text-gray-600">
              <XCircle className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-gray-500 dark:text-gray-400">Action</p>
              <p className="font-medium text-gray-900 dark:text-white">{selectedLog.action}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Actor</p>
              <p className="font-medium text-gray-900 dark:text-white">{selectedLog.actor} ({selectedLog.actor_type})</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Target</p>
              <p className="font-medium text-gray-900 dark:text-white">{selectedLog.target}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Input Hash</p>
              <p className="font-mono text-xs text-gray-700 dark:text-gray-300">{selectedLog.input_hash || '—'}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Output Hash</p>
              <p className="font-mono text-xs text-gray-700 dark:text-gray-300">{selectedLog.output_hash || '—'}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Radix TX Ref</p>
              <p className="font-mono text-xs text-gray-700 dark:text-gray-300">
                {selectedLog.radix_tx_ref ? (
                  <span className="flex items-center gap-1">
                    {selectedLog.radix_tx_ref} <ExternalLink className="h-3 w-3" />
                  </span>
                ) : '—'}
              </p>
            </div>
          </div>
          {selectedLog.anchored && (
            <div className="mt-3 rounded-lg bg-green-50 p-3 dark:bg-green-900/20">
              <p className="text-xs text-green-800 dark:text-green-300">
                <CheckCircle className="inline h-3.5 w-3.5 mr-1" />
                This entry is anchored to the Radix DLT. The hash can be independently verified by anyone.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
