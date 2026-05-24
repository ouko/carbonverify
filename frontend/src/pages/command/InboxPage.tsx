import { useState } from 'react'
import {
  CheckCircle, XCircle, HelpCircle, ArrowUpCircle, UserCheck,
  Clock, AlertTriangle, TrendingUp,
} from 'lucide-react'
import { usePriorityQueue } from '../../hooks/useCommandData'
import { useCommandWebSocket } from '../../hooks/useCommandWebSocket'

export function InboxPage() {
  const { data: items, isLoading } = usePriorityQueue()
  const [selectedItem, setSelectedItem] = useState<any>(null)
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  useCommandWebSocket()

  const filtered = (items || []).filter((item: any) => {
    if (filterType !== 'all' && item.itemType !== filterType) return false
    if (filterStatus !== 'all' && item.status !== filterStatus) return false
    return true
  })

  const getPriorityColor = (p: number) => {
    if (p === 5) return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
    if (p === 4) return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300'
    if (p === 3) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'
    return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'calculation': return <TrendingUp className="h-4 w-4" />
      case 'report': return <AlertTriangle className="h-4 w-4" />
      case 'data_anomaly': return <AlertTriangle className="h-4 w-4 text-red-500" />
      case 'agent_review': return <HelpCircle className="h-4 w-4" />
      case 'vvb_response': return <ArrowUpCircle className="h-4 w-4" />
      default: return <HelpCircle className="h-4 w-4" />
    }
  }

  return (
    <div className="flex h-full gap-4">
      {/* Queue Table */}
      <div className={`flex flex-col ${selectedItem ? 'w-3/5' : 'w-full'} overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800`}>
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-800 dark:text-white">Priority Queue</h2>
            <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
              {filtered.length} items
            </span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">All Types</option>
              <option value="calculation">Calculation</option>
              <option value="report">Report</option>
              <option value="data_anomaly">Data Anomaly</option>
              <option value="agent_review">Agent Review</option>
              <option value="vvb_response">VVB Response</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="in_review">In Review</option>
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Priority</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Project</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Type</th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Reason</th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Conf</th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Queue</th>
                <th className="px-3 py-2 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {isLoading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No items in queue</td></tr>
              ) : (
                filtered.map((item: any) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className={`cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50 ${
                      selectedItem?.id === item.id ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''
                    }`}
                  >
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ${getPriorityColor(item.priority)}`}>
                        P{item.priority}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-sm text-gray-900 dark:text-white">
                      <div className="font-medium">{item.projectName}</div>
                      <div className="text-xs text-gray-500">${item.financialImpact.toLocaleString()}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
                        {getTypeIcon(item.itemType)}
                        <span className="capitalize">{item.itemType.replace('_', ' ')}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-gray-600 dark:text-gray-300 max-w-[200px] truncate">
                      {item.reason}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs">
                      <span className={item.confidence < 0.85 ? 'text-red-600 font-semibold' : 'text-gray-600 dark:text-gray-300'}>
                        {Math.round(item.confidence * 100)}%
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right text-xs text-gray-500 dark:text-gray-400">
                      <div className="flex items-center justify-end gap-1">
                        <Clock className="h-3 w-3" />
                        {item.hoursInQueue}h
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <div className="flex justify-center gap-1">
                        <button title="Approve" className="rounded p-1 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20">
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button title="Request Info" className="rounded p-1 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20">
                          <HelpCircle className="h-4 w-4" />
                        </button>
                        <button title="Escalate" className="rounded p-1 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20">
                          <ArrowUpCircle className="h-4 w-4" />
                        </button>
                        <button title="Assign to Me" className="rounded p-1 text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20">
                          <UserCheck className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Context Panel */}
      {selectedItem && (
        <div className="w-2/5 overflow-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-700">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-800 dark:text-white">Context</h3>
              <button onClick={() => setSelectedItem(null)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="h-4 w-4" />
              </button>
            </div>
          </div>
          <div className="space-y-4 p-4">
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Project</p>
              <p className="text-sm font-medium text-gray-900 dark:text-white">{selectedItem.projectName}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Issue</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">{selectedItem.reason}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Confidence Score</p>
              <div className="mt-1 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-2 rounded-full ${selectedItem.confidence < 0.85 ? 'bg-red-500' : 'bg-green-500'}`}
                  style={{ width: `${selectedItem.confidence * 100}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">{Math.round(selectedItem.confidence * 100)}%</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Financial Impact</p>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">${selectedItem.financialImpact.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Suggested Action</p>
              <p className="text-sm text-indigo-600 dark:text-indigo-400">{selectedItem.suggestedAction}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Time in Queue</p>
              <p className="text-sm text-gray-700 dark:text-gray-300">{selectedItem.hoursInQueue} hours</p>
            </div>

            <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700/50">
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Recent Activity</p>
              <div className="mt-2 space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  <span className="text-gray-600 dark:text-gray-300">Calculation completed — 2h ago</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="h-1.5 w-1.5 rounded-full bg-yellow-500" />
                  <span className="text-gray-600 dark:text-gray-300">Methodology score 68% — flagged</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                  <span className="text-gray-600 dark:text-gray-300">Data sources uploaded — 1d ago</span>
                </div>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button className="flex-1 rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700">
                Approve
              </button>
              <button className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
                Request Info
              </button>
            </div>
            <div className="flex gap-2">
              <button className="flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700">
                Escalate
              </button>
              <button className="flex-1 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                Assign to Me
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
