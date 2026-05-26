import { useState, useMemo } from 'react'
import { ArrowUpDown, Search, FolderOpen } from 'lucide-react'
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
    if (overdue) return <span className="badge badge-red animate-pulse text-[10px]">OVERDUE</span>
    if (level === 'green') return <span className="badge badge-green text-[10px]">Ready</span>
    if (level === 'yellow') return <span className="badge badge-amber text-[10px]">At Risk</span>
    return <span className="badge badge-red text-[10px]">Blocked</span>
  }

  const getStatusDot = (status: string) => {
    const colors: Record<string, string> = {
      onboarding: 'bg-surface-400',
      data_collection: 'bg-blue-400',
      calculation: 'bg-violet-400',
      review: 'bg-amber-400',
      submitted: 'bg-purple-400',
      verified: 'bg-primary-400',
      monitoring: 'bg-cyan-400',
    }
    return <span className={`inline-block h-2 w-2 rounded-full ${colors[status] || 'bg-surface-400'}`} />
  }

  const stats = {
    total: (projects || []).length,
    green: (projects || []).filter((p: any) => p.alertLevel === 'green').length,
    yellow: (projects || []).filter((p: any) => p.alertLevel === 'yellow').length,
    red: (projects || []).filter((p: any) => p.alertLevel === 'red' || p.overdue).length,
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="card p-5">
          <p className="text-xs text-surface-400 dark:text-surface-500">Total Projects</p>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats.total}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-primary-600 dark:text-primary-400">Ready</p>
          <p className="text-2xl font-bold text-primary-700 dark:text-primary-300">{stats.green}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-amber-600 dark:text-amber-400">At Risk</p>
          <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{stats.yellow}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-red-600 dark:text-red-400">Blocked / Overdue</p>
          <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.red}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 card p-3">
        <div className="flex items-center rounded-xl bg-surface-100/80 dark:bg-surface-800/50 px-3 py-2">
          <Search className="h-3.5 w-3.5 text-surface-400" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ml-2 w-40 bg-transparent text-xs text-surface-700 outline-none placeholder:text-surface-400 dark:text-surface-200"
          />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer">
          <option value="all">All Statuses</option>
          <option value="onboarding">Onboarding</option>
          <option value="data_collection">Data Collection</option>
          <option value="calculation">Calculation</option>
          <option value="review">Review</option>
          <option value="submitted">Submitted</option>
          <option value="verified">Verified</option>
          <option value="monitoring">Monitoring</option>
        </select>
        <select value={methodologyFilter} onChange={(e) => setMethodologyFilter(e.target.value)} className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer">
          <option value="all">All Methodologies</option>
          <option value="TPDDTEC_v4">TPDDTEC v4</option>
          <option value="VM0050">VM0050</option>
          <option value="VMR0006">VMR0006</option>
          <option value="AMS-II.G">AMS-II.G</option>
        </select>
        <select value={alertFilter} onChange={(e) => setAlertFilter(e.target.value)} className="input-modern py-1.5 px-2 text-xs appearance-none cursor-pointer">
          <option value="all">All Alerts</option>
          <option value="green">Ready</option>
          <option value="yellow">At Risk</option>
          <option value="red">Blocked</option>
        </select>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-50 dark:bg-surface-900">
              <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                {[
                  { key: 'name', label: 'Project' },
                  { key: 'status', label: 'Status' },
                  { key: 'readiness', label: 'Readiness %' },
                  { key: 'creditsForecast', label: 'Credits Forecast' },
                  { key: 'lastActivityDays', label: 'Last Activity' },
                  { key: 'alertLevel', label: 'Alert' },
                ].map((col) => (
                  <th key={col.key} onClick={() => toggleSort(col.key)} className="cursor-pointer px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                    <div className="flex items-center gap-1">{col.label}<ArrowUpDown className="h-3 w-3" /></div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
              {isLoading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-surface-400">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-12 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                      <FolderOpen className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                    </div>
                    <p className="text-sm text-surface-400">No projects match filters</p>
                  </div>
                </td></tr>
              ) : (
                filtered.map((p: any) => (
                  <tr key={p.id} onClick={() => navigate(`/projects/${p.id}`)} className="cursor-pointer transition-colors hover:bg-surface-50/50 dark:hover:bg-surface-800/30">
                    <td className="px-3 py-2.5">
                      <div className="text-sm font-semibold text-surface-900 dark:text-surface-100">{p.name}</div>
                      <div className="text-xs text-surface-400">{p.methodology} • {p.developer}</div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <div className="flex items-center gap-1.5 text-xs text-surface-600 dark:text-surface-300">
                        {getStatusDot(p.status)}
                        <span className="capitalize">{(p.status || '').replace('_', ' ')}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
                          <div className={`h-1.5 rounded-full ${p.readiness > 90 ? 'bg-primary-500' : p.readiness > 70 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${p.readiness}%` }} />
                        </div>
                        <span className="text-xs font-medium text-surface-700 dark:text-surface-300">{p.readiness}%</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-sm text-surface-900 dark:text-surface-100">{p.creditsForecast.toLocaleString()} tCO₂e</td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-xs text-surface-400 dark:text-surface-500">{p.lastActivityDays === 0 ? 'Today' : `${p.lastActivityDays}d ago`}</td>
                    <td className="whitespace-nowrap px-3 py-2.5">{getAlertBadge(p.alertLevel, p.overdue)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
