import { useState } from 'react'
import {
  Target, Search, Filter, ExternalLink, X, ArrowRight, Phone, Mail, MapPin,
  Activity, Gauge, Clock, CheckCircle, BarChart3, RefreshCw, AlertTriangle, Wifi, WifiOff,
} from 'lucide-react'
import { useLeads, useUpdateLead, useLeadsStats, useScrapeLeads, useScraperHealth, useScraperHistory } from '../hooks/useLeads'
import type { Lead, LeadWorkflowStatus, LeadPriority } from '../types'

const REGISTRY_LABELS: Record<string, string> = {
  verra: 'Verra',
  gold_standard: 'Gold Standard',
  cdm: 'CDM',
  kenya_national: 'Kenya National',
  manual: 'Manual',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'badge-slate',
  medium: 'badge-blue',
  high: 'badge-amber',
  critical: 'badge-red',
}

const LEAD_STATUS_COLORS: Record<string, string> = {
  new: 'badge-slate',
  contacted: 'badge-blue',
  qualified: 'badge-amber',
  proposal_sent: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
  converted: 'badge-green',
  dismissed: 'badge-red',
}

const KANBAN_COLUMNS: LeadWorkflowStatus[] = ['new', 'contacted', 'qualified', 'proposal_sent', 'converted']

function StuckScoreBar({ score }: { score: number }) {
  const color = score >= 76 ? 'bg-red-500' : score >= 56 ? 'bg-amber-500' : score >= 31 ? 'bg-blue-500' : 'bg-primary-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${Math.min(score, 100)}%` }} />
      </div>
      <span className="text-xs font-semibold text-surface-700 dark:text-surface-300 tabular-nums">{score.toFixed(1)}</span>
    </div>
  )
}

function LeadDetailModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const updateLead = useUpdateLead()
  const [notes, setNotes] = useState(lead.notes || '')
  const [leadStatus, setLeadStatus] = useState<LeadWorkflowStatus>(lead.lead_status)
  const [priority, setPriority] = useState<LeadPriority>(lead.priority)

  const handleSave = () => {
    updateLead.mutate({
      id: lead.id,
      updates: { notes, lead_status: leadStatus, priority },
    })
    onClose()
  }

  const scoreBreakdown = [
    { label: 'Time in Stage', value: `${lead.days_in_status || 0} days`, weight: '40 pts max' },
    { label: 'Deadline Proximity', value: lead.crediting_period_end || 'N/A', weight: '25 pts max' },
    { label: 'Verification Gap', value: lead.last_verification_date || 'N/A', weight: '20 pts max' },
    { label: 'Methodology Complexity', value: lead.methodology || 'N/A', weight: '15 pts max' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary-500" />
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Lead Details</h3>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5">
          {/* Header info */}
          <div className="flex items-start justify-between">
            <div>
              <h4 className="text-base font-semibold text-surface-900 dark:text-surface-100">{lead.project_name}</h4>
              <div className="flex items-center gap-2 mt-1.5 text-xs text-surface-400 dark:text-surface-500">
                <span className={`badge ${PRIORITY_COLORS[lead.priority]}`}>{lead.priority}</span>
                <span className="badge badge-slate">{REGISTRY_LABELS[lead.registry_source]}</span>
                <span className="badge badge-slate">{lead.external_id}</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-surface-900 dark:text-surface-100">{lead.stuck_score.toFixed(1)}</div>
              <div className="text-[10px] uppercase tracking-wider text-surface-400">Stuck Score</div>
            </div>
          </div>

          {/* Developer info */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Developer</p>
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100">{lead.project_developer || 'Unknown'}</p>
              {lead.developer_contact && (
                <p className="text-xs text-surface-500 flex items-center gap-1 mt-1">
                  <Phone className="h-3 w-3" /> {lead.developer_contact}
                </p>
              )}
              {lead.developer_email && (
                <p className="text-xs text-surface-500 flex items-center gap-1 mt-0.5">
                  <Mail className="h-3 w-3" /> {lead.developer_email}
                </p>
              )}
            </div>
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Location</p>
              <p className="text-sm font-medium text-surface-900 dark:text-surface-100 flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" /> {lead.country}{lead.region ? `, ${lead.region}` : ''}
              </p>
              <p className="text-xs text-surface-500 mt-1">Methodology: {lead.methodology || 'N/A'}</p>
              <p className="text-xs text-surface-500">Sector: {lead.sector || 'N/A'}</p>
            </div>
          </div>

          {/* Status & Period */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Registry Status</p>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100 capitalize">{lead.status.replace('_', ' ')}</p>
            </div>
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Days in Stage</p>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{lead.days_in_status ?? 'N/A'}</p>
            </div>
            <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
              <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Est. Credits/yr</p>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{lead.estimated_credits_per_year?.toLocaleString() ?? 'N/A'}</p>
            </div>
          </div>

          {/* Crediting period */}
          <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
            <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Crediting Period</p>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-surface-600 dark:text-surface-300">{lead.crediting_period_start || 'N/A'}</span>
              <ArrowRight className="h-3.5 w-3.5 text-surface-400" />
              <span className="text-surface-600 dark:text-surface-300">{lead.crediting_period_end || 'N/A'}</span>
              {lead.crediting_period_end && new Date(lead.crediting_period_end) < new Date() && (
                <span className="badge badge-red text-[10px]">Expired</span>
              )}
              {lead.crediting_period_end && new Date(lead.crediting_period_end) > new Date() && new Date(lead.crediting_period_end) < new Date(Date.now() + 180 * 86400000) && (
                <span className="badge badge-amber text-[10px]">&lt; 180 days</span>
              )}
            </div>
          </div>

          {/* Score breakdown */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-2">Scoring Breakdown</p>
            <div className="grid grid-cols-2 gap-2">
              {scoreBreakdown.map((item) => (
                <div key={item.label} className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
                  <p className="text-[10px] text-surface-400 dark:text-surface-500">{item.label}</p>
                  <p className="text-sm font-medium text-surface-900 dark:text-surface-100">{item.value}</p>
                  <p className="text-[10px] text-surface-400">{item.weight}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Registry link */}
          {lead.registry_url && (
            <a href={lead.registry_url} target="_blank" rel="noopener noreferrer" className="btn-ghost w-full justify-center text-xs">
              <ExternalLink className="h-3.5 w-3.5" /> View on {REGISTRY_LABELS[lead.registry_source]}
            </a>
          )}

          {/* Edit controls */}
          <div className="border-t border-surface-100 dark:border-surface-800/50 pt-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Lead Status</label>
                <select value={leadStatus} onChange={(e) => setLeadStatus(e.target.value as LeadWorkflowStatus)} className="input-modern appearance-none cursor-pointer text-sm">
                  <option value="new">New</option>
                  <option value="contacted">Contacted</option>
                  <option value="qualified">Qualified</option>
                  <option value="proposal_sent">Proposal Sent</option>
                  <option value="converted">Converted</option>
                  <option value="dismissed">Dismissed</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Priority Override</label>
                <select value={priority} onChange={(e) => setPriority(e.target.value as LeadPriority)} className="input-modern appearance-none cursor-pointer text-sm">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Notes</label>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="input-modern text-sm" placeholder="Add notes about this lead..." />
            </div>
            <div className="flex gap-2">
              <button onClick={onClose} className="btn-secondary flex-1 text-sm">Cancel</button>
              <button onClick={handleSave} className="btn-primary flex-1 text-sm">
                <CheckCircle className="h-4 w-4 mr-1" /> Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ScraperStatusBadge({ status, message }: { status: string; message: string }) {
  const isHealthy = status === 'healthy'
  const isDemo = status === 'demo'
  return (
    <div className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium ${
      isHealthy ? 'bg-primary-50 text-primary-700 dark:bg-primary-950/30 dark:text-primary-300' :
      isDemo ? 'bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400' :
      'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300'
    }`} title={message}>
      {isHealthy ? <Wifi className="h-3 w-3" /> : isDemo ? <WifiOff className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      <span className="capitalize">{status}</span>
    </div>
  )
}

export default function LeadsPage() {
  const [view, setView] = useState<'table' | 'kanban'>('table')
  const [search, setSearch] = useState('')
  const [registryFilter, setRegistryFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)

  const filters: Record<string, string> = {}
  if (registryFilter !== 'all') filters.registry_source = registryFilter
  if (priorityFilter !== 'all') filters.priority = priorityFilter
  if (statusFilter !== 'all') filters.lead_status = statusFilter
  if (search) filters.search = search

  const { data: leads, isLoading } = useLeads(filters)
  const { data: stats } = useLeadsStats()
  const { data: health } = useScraperHealth()
  const { data: history } = useScraperHistory()
  const scrapeMutation = useScrapeLeads()

  const kanbanLeads = (status: LeadWorkflowStatus) => leads?.filter((l) => l.lead_status === status) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="page-title">Lead Intelligence</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Monitor and score potential clients from carbon registries
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:items-end">
          {/* Scraper status */}
          {health && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500">Scrapers:</span>
              <ScraperStatusBadge status={health.verra?.status || 'unknown'} message={health.verra?.message || ''} />
              <ScraperStatusBadge status={health.gold_standard?.status || 'unknown'} message={health.gold_standard?.message || ''} />
              <ScraperStatusBadge status={health.cdm?.status || 'unknown'} message={health.cdm?.message || ''} />
              {health.mode === 'demo' && (
                <span className="text-[10px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 px-2 py-0.5 rounded">Demo mode</span>
              )}
            </div>
          )}
          {/* Last scraped info */}
          {history && (
            <div className="flex items-center gap-3 flex-wrap text-[11px] text-surface-400 dark:text-surface-500">
              {(['verra', 'gold_standard', 'cdm'] as const).map((source) => {
                const entry = history[source]
                if (!entry) return null
                const label = source === 'gold_standard' ? 'Gold Standard' : source.charAt(0).toUpperCase() + source.slice(1)
                const time = entry.scraped_at ? new Date(entry.scraped_at).toLocaleString() : 'Never'
                return (
                  <span key={source} className="flex items-center gap-1" title={`${entry.count} leads (${entry.created} new, ${entry.updated} updated)`}>
                    <Clock className="h-3 w-3" />
                    {label}: {time} · {entry.count} results
                  </span>
                )
              })}
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => scrapeMutation.mutate({ country: 'Kenya' })}
              disabled={scrapeMutation.isPending}
              className="btn-primary text-sm disabled:opacity-50"
            >
              {scrapeMutation.isPending ? (
                <><RefreshCw className="h-4 w-4 mr-1 animate-spin" /> Scraping...</>
              ) : (
                <><RefreshCw className="h-4 w-4 mr-1" /> Run Scrape</>
              )}
            </button>
            <button onClick={() => setView(view === 'table' ? 'kanban' : 'table')} className="btn-secondary text-sm">
              {view === 'table' ? <BarChart3 className="h-4 w-4 mr-1" /> : <Activity className="h-4 w-4 mr-1" />}
              {view === 'table' ? 'Kanban View' : 'Table View'}
            </button>
          </div>
        </div>
      </div>

      {/* Scrape Report */}
      {scrapeMutation.data && (
        <div className="card p-4 border-l-4 border-primary-500">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
              Scrape Report — {scrapeMutation.data.created} created, {scrapeMutation.data.updated} updated
            </h3>
            <button
              onClick={() => scrapeMutation.reset()}
              className="text-xs text-surface-400 hover:text-surface-600 dark:hover:text-surface-300"
            >
              Dismiss
            </button>
          </div>
          <div className="space-y-2">
            {scrapeMutation.data.per_source.map((s) => (
              <div key={s.source} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="capitalize font-medium text-surface-700 dark:text-surface-300">
                    {s.source.replace('_', ' ')}
                  </span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                    s.status === 'live'
                      ? 'bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-300'
                      : s.status === 'error'
                      ? 'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
                  }`}>
                    {s.status}
                  </span>
                </div>
                <div className="text-surface-500 dark:text-surface-400 text-xs">
                  {s.count} leads
                  {s.created > 0 && <span className="text-green-600 dark:text-green-400 ml-1">({s.created} new)</span>}
                  {s.updated > 0 && <span className="text-blue-600 dark:text-blue-400 ml-1">({s.updated} updated)</span>}
                  {s.error && <span className="text-red-500 ml-1" title={s.error}>— error</span>}
                </div>
              </div>
            ))}
          </div>
          {scrapeMutation.data.per_source.some((s) => s.status === 'demo') && (
            <p className="text-[11px] text-surface-400 dark:text-surface-500 mt-2">
              Some sources returned demo data because live scraping is blocked. Set LEAD_SCRAPER_MODE=live and install Playwright for real registry data.
            </p>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Target className="w-4.5 h-4.5 text-primary-600 dark:text-primary-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Total Leads</span>
          </div>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.total_leads ?? 0}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-red-50 dark:bg-red-950/30 flex items-center justify-center">
              <Gauge className="w-4.5 h-4.5 text-red-600 dark:text-red-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">High Priority</span>
          </div>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.high_priority_count ?? 0}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-amber-50 dark:bg-amber-950/30 flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-amber-600 dark:text-amber-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Avg Stuck Score</span>
          </div>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.avg_stuck_score ?? 0}</p>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
              <Clock className="w-4.5 h-4.5 text-blue-600 dark:text-blue-400" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Critical</span>
          </div>
          <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stats?.critical_count ?? 0}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Search projects or developers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-modern pl-10"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-surface-400" />
            <select value={registryFilter} onChange={(e) => setRegistryFilter(e.target.value)} className="input-modern pl-8 pr-6 py-2 text-xs appearance-none cursor-pointer">
              <option value="all">All Registries</option>
              <option value="verra">Verra</option>
              <option value="gold_standard">Gold Standard</option>
              <option value="cdm">CDM</option>
            </select>
          </div>
          <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} className="input-modern py-2 px-3 text-xs appearance-none cursor-pointer">
            <option value="all">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input-modern py-2 px-3 text-xs appearance-none cursor-pointer">
            <option value="all">All Lead Status</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="proposal_sent">Proposal Sent</option>
            <option value="converted">Converted</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="relative">
            <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
          </div>
        </div>
      ) : view === 'table' ? (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Project</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Registry</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Developer</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Days</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Stuck Score</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Priority</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Lead Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {leads?.map((lead) => (
                  <tr
                    key={lead.id}
                    onClick={() => setSelectedLead(lead)}
                    className="cursor-pointer hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-semibold text-surface-900 dark:text-surface-100">{lead.project_name}</p>
                        <p className="text-xs text-surface-400 dark:text-surface-500">{lead.country}{lead.region ? `, ${lead.region}` : ''}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="badge badge-slate text-[10px]">{REGISTRY_LABELS[lead.registry_source]}</span>
                    </td>
                    <td className="px-6 py-4 text-surface-600 dark:text-surface-300 text-xs">
                      {lead.project_developer || '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className="badge badge-slate text-[10px] capitalize">{lead.status.replace('_', ' ')}</span>
                    </td>
                    <td className="px-6 py-4 text-surface-600 dark:text-surface-300 text-xs">
                      {lead.days_in_status ?? '—'}
                    </td>
                    <td className="px-6 py-4">
                      <StuckScoreBar score={lead.stuck_score} />
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${PRIORITY_COLORS[lead.priority]} text-[10px]`}>{lead.priority}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${LEAD_STATUS_COLORS[lead.lead_status]} text-[10px] capitalize`}>{lead.lead_status.replace('_', ' ')}</span>
                    </td>
                  </tr>
                ))}
                {leads?.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                          <Target className="w-6 h-6 text-surface-400 dark:text-surface-500" />
                        </div>
                        <div className="text-sm text-surface-500 dark:text-surface-400">No leads found.</div>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {KANBAN_COLUMNS.map((col) => {
            const colLeads = kanbanLeads(col)
            return (
              <div key={col} className="flex w-72 min-w-[18rem] flex-col">
                <div className="mb-2 rounded-xl px-3 py-2 bg-surface-100 dark:bg-surface-800/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-surface-700 dark:text-surface-200 capitalize">{col.replace('_', ' ')}</span>
                    <span className="rounded-full bg-white dark:bg-surface-800 px-2 py-0.5 text-xs font-bold text-surface-600 dark:text-surface-300 shadow-sm">{colLeads.length}</span>
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2">
                  {colLeads.map((lead) => (
                    <div
                      key={lead.id}
                      onClick={() => setSelectedLead(lead)}
                      className="cursor-pointer rounded-xl border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 p-3 transition-all hover:shadow-soft"
                    >
                      <div className="flex items-start justify-between mb-1.5">
                        <p className="text-xs font-semibold text-surface-900 dark:text-surface-100 line-clamp-1">{lead.project_name}</p>
                        <span className={`badge ${PRIORITY_COLORS[lead.priority]} text-[10px]`}>{lead.priority.slice(0, 1).toUpperCase()}</span>
                      </div>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 mb-1.5">{lead.project_developer || 'Unknown developer'}</p>
                      <div className="flex items-center justify-between">
                        <span className="badge badge-slate text-[10px]">{REGISTRY_LABELS[lead.registry_source]}</span>
                        <StuckScoreBar score={lead.stuck_score} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {selectedLead && (
        <LeadDetailModal lead={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  )
}
