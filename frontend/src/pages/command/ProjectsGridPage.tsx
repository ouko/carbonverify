import { useState, useMemo } from 'react'
import { ArrowUpDown, Search } from 'lucide-react'
import { useProjectsHealth } from '../../hooks/useCommandData'
import { useNavigate } from 'react-router-dom'

export function ProjectsGridPage() {
  const { data: projects, isLoading } = useProjectsHealth()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [methodologyFilter, setMethodologyFilter] = useState('all')
  const [alertFilter, setAlertFilter] = useState('all')
  const [sortKey, setSortKey] = useState<string>('readiness')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const filtered = useMemo(() => {
    const list = (projects || []).filter((p: any) => {
      if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
      if (statusFilter !== 'all' && p.status !== statusFilter) return false
      if (methodologyFilter !== 'all' && p.methodology !== methodologyFilter) return false
      if (alertFilter !== 'all' && p.alertLevel !== alertFilter) return false
      return true
    })
    list.sort((a: any, b: any) => {
      const av = a[sortKey] ?? 0
      const bv = b[sortKey] ?? 0
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
    })
    return list
  }, [projects, search, statusFilter, methodologyFilter, alertFilter, sortKey, sortDir])

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  const getAlertBadge = (level: string, overdue: boolean) => {
    if (overdue) return <span className="inline-flex animate-pulse rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white">OVERDUE</span>
    if (level === 'green') return <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300">Ready</span>
    if (level === 'yellow') return <span className="inline-flex rounded-full bg-yellow-100 px-2 py-0.5 text-[10px] font-medium text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">At Risk</span>
    return <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-medium text-red-800 dark:bg-red-900/30 dark:text-red-300">Blocked</span>
  }

  const getStatusDot = (status: string) => {
    const colors: Record<string, string> = {
      onboarding: 'bg-gray-400',
      data_collection: 'bg-blue-400',
      calculation: 'bg-indigo-400',
      review: 'bg-yellow-400',
      submitted: 'bg-purple-400',
      verified: 'bg-green-400',
      monitoring: 'bg-teal-400',
    }
    return <span className={`inline-block h-2 w-2 rounded-full ${colors[status] || 'bg-gray-400'}`} />
  }

  const stats = {
    total: (projects || []).length,
    green: (projects || []).filter((p: any) => p.alertLevel === 'green').length,
    yellow: (projects || []).filter((p: any) => p.alertLevel === 'yellow').length,
    red: (projects || []).filter((p: any) => p.alertLevel === 'red' || p.overdue).length,
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-xs text-gray-500 dark:text-gray-400">Total Projects</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-xs text-green-600 dark:text-green-400">Ready</p>
          <p className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.green}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-xs text-yellow-600 dark:text-yellow-400">At Risk</p>
          <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{stats.yellow}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-xs text-red-600 dark:text-red-400">Blocked / Overdue</p>
          <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.red}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center rounded-md bg-gray-100 px-2 py-1 dark:bg-gray-700">
          <Search className="h-3.5 w-3.5 text-gray-400" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 w-40 bg-transparent text-xs text-gray-700 outline-none placeholder:text-gray-400 dark:text-gray-200"
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white">
          <option value="all">All Statuses</option>
          <option value="onboarding">Onboarding</option>
          <option value="data_collection">Data Collection</option>
          <option value="calculation">Calculation</option>
          <option value="review">Review</option>
          <option value="submitted">Submitted</option>
          <option value="verified">Verified</option>
          <option value="monitoring">Monitoring</option>
        </select>
        <select value={methodologyFilter} onChange={(e) => setMethodologyFilter(e.target.value)} className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white">
          <option value="all">All Methodologies</option>
          <option value="TPDDTEC_v4">TPDDTEC v4</option>
          <option value="VM0050">VM0050</option>
          <option value="VMR0006">VMR0006</option>
          <option value="AMS-II.G">AMS-II.G</option>
        </select>
        <select value={alertFilter} onChange={(e) => setAlertFilter(e.target.value)} className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs dark:border-gray-600 dark:bg-gray-700 dark:text-white">
          <option value="all">All Alerts</option>
          <option value="green">Ready</option>
          <option value="yellow">At Risk</option>
          <option value="red">Blocked</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              {[
                { key: 'name', label: 'Project' },
                { key: 'status', label: 'Status' },
                { key: 'readiness', label: 'Readiness %' },
                { key: 'creditsForecast', label: 'Credits Forecast' },
                { key: 'lastActivityDays', label: 'Last Activity' },
                { key: 'alertLevel', label: 'Alert' },
              ].map((col) => (
                <th key={col.key} onClick={() => toggleSort(col.key)} className="cursor-pointer px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800">
                  <div className="flex items-center gap-1">{col.label}<ArrowUpDown className="h-3 w-3" /></div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {isLoading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-500">No projects match filters</td></tr>
            ) : (
              filtered.map((p: any) => (
                <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)} className="cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-3 py-2.5">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{p.name}</div>
                    <div className="text-xs text-gray-500">{p.methodology} • {p.developer}</div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
                      {getStatusDot(p.status)}
                      <span className="capitalize">{p.status.replace('_', ' ')}</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 rounded-full bg-gray-200 dark:bg-gray-700">
                        <div className={`h-1.5 rounded-full ${p.readiness > 90 ? 'bg-green-500' : p.readiness > 70 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${p.readiness}%` }} />
                      </div>
                      <span className="text-xs font-medium text-gray-700 dark:text-gray-300">{p.readiness}%</span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-sm text-gray-900 dark:text-white">{p.creditsForecast.toLocaleString()} tCO₂e</td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-xs text-gray-500 dark:text-gray-400">{p.lastActivityDays === 0 ? 'Today' : `${p.lastActivityDays}d ago`}</td>
                  <td className="whitespace-nowrap px-3 py-2.5">{getAlertBadge(p.alertLevel, p.overdue)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
