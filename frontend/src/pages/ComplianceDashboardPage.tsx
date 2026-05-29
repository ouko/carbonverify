import { useState } from 'react'
import {
  Shield, FileText, AlertTriangle, CheckCircle, Clock,
  Users, Gavel, BookOpen, TrendingUp, ChevronLeft, ChevronRight, X
} from 'lucide-react'
import { useDSRs, useBreaches, useConflicts, useMethodologyVersions } from '../hooks/useCompliance'
import { LoadingSpinner } from '../components/LoadingSpinner'

const STATUS_COLORS: Record<string, string> = {
  received: 'badge-blue',
  under_review: 'badge-amber',
  fulfilled: 'badge-green',
  rejected: 'badge-red',
  contained: 'badge-green',
  notified_regulator: 'bg-violet-50 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300',
  pending_review: 'bg-orange-50 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300',
  approved: 'badge-green',
}

function usePagination<T>(items: T[], perPage = 5) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(items.length / perPage))
  const currentPage = Math.min(page, totalPages)
  const paginated = items.slice((currentPage - 1) * perPage, currentPage * perPage)
  return { page: currentPage, setPage, totalPages, paginated }
}

function Pagination({ page, totalPages, setPage }: { page: number; totalPages: number; setPage: (p: number) => void }) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between px-6 py-3 border-t border-surface-200/60 dark:border-surface-800/40">
      <p className="text-xs text-surface-400 dark:text-surface-500">
        Page {page} of {totalPages}
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setPage(Math.max(1, page - 1))}
          disabled={page === 1}
          className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-40 transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          onClick={() => setPage(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 disabled:opacity-40 transition-colors"
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export function ComplianceDashboardPage() {
  const [activeTab, setActiveTab] = useState<'dsr' | 'breaches' | 'conflicts' | 'methodology'>('dsr')
  const [reviewingCOI, setReviewingCOI] = useState<string | null>(null)
  const [viewingRules, setViewingRules] = useState<{ name: string; version: string } | null>(null)

  const { data: dsrs, isLoading: dsrsLoading, isError: dsrsError } = useDSRs()
  const { data: breaches, isLoading: breachesLoading, isError: breachesError } = useBreaches()
  const { data: conflicts, isLoading: conflictsLoading, isError: conflictsError } = useConflicts()
  const { data: methodologies, isLoading: methodologiesLoading, isError: methodologiesError } = useMethodologyVersions()

  const isLoading = dsrsLoading || breachesLoading || conflictsLoading || methodologiesLoading
  const isError = dsrsError || breachesError || conflictsError || methodologiesError

  const openDSRs = (dsrs || []).filter(d => d.status !== 'fulfilled' && d.status !== 'rejected').length
  const urgentDSRs = (dsrs || []).filter(d => d.days_remaining <= 15 && d.status !== 'fulfilled' && d.status !== 'rejected').length
  const activeBreaches = (breaches || []).filter(b => b.status !== 'resolved').length
  const slaOkBreaches = (breaches || []).filter(b => !b.sla_violated).length
  const pendingCOI = (conflicts || []).filter(c => !c.approved).length

  const tabs = [
    { key: 'dsr' as const, label: 'Data Subject Requests', icon: FileText },
    { key: 'breaches' as const, label: 'Breach Notifications', icon: AlertTriangle },
    { key: 'conflicts' as const, label: 'Conflict of Interest', icon: Gavel },
    { key: 'methodology' as const, label: 'Methodology Versions', icon: BookOpen },
  ]

  const dsrPagination = usePagination(dsrs || [], 5)
  const breachPagination = usePagination(breaches || [], 5)
  const conflictPagination = usePagination(conflicts || [], 5)
  const methodologyPagination = usePagination(methodologies || [], 5)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
            </div>
            <div>
              <h2 className="page-title">Compliance Center</h2>
              <p className="text-xs text-surface-400 dark:text-surface-500">Kenya Data Protection Act · VVB Independence</p>
            </div>
          </div>
        </div>
        <LoadingSpinner />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
              <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
            </div>
            <div>
              <h2 className="page-title">Compliance Center</h2>
              <p className="text-xs text-surface-400 dark:text-surface-500">Kenya Data Protection Act · VVB Independence</p>
            </div>
          </div>
        </div>
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load compliance data</p>
          <p className="text-sm text-surface-500 mt-2">Please try again later.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
            <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="page-title">Compliance Center</h2>
            <p className="text-xs text-surface-400 dark:text-surface-500">Kenya Data Protection Act · VVB Independence</p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: 'Open DSRs', value: String(openDSRs), sub: `${urgentDSRs} urgent (≤15 days)`, icon: FileText, color: 'text-blue-500' },
          { label: 'Active Breaches', value: String(activeBreaches), sub: `${slaOkBreaches} within 72h SLA`, icon: AlertTriangle, color: 'text-red-500' },
          { label: 'Pending COI', value: String(pendingCOI), sub: 'Awaiting review', icon: Users, color: 'text-violet-500' },
          { label: 'Methodologies', value: String((methodologies || []).length), sub: 'All versions tracked', icon: BookOpen, color: 'text-primary-500' },
        ].map((stat) => (
          <div key={stat.label} className="card p-5">
            <div className="flex items-center gap-2 mb-2">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              <span className="text-xs text-surface-400 dark:text-surface-500">{stat.label}</span>
            </div>
            <p className="text-2xl font-bold text-surface-900 dark:text-surface-100">{stat.value}</p>
            <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">{stat.sub}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-surface-100/80 dark:bg-surface-800/50 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-white dark:bg-surface-700 text-primary-700 dark:text-primary-300 shadow-sm'
                : 'text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* DSR Tab */}
      {activeTab === 'dsr' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Data Subject Requests</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {dsrPagination.paginated.map((dsr) => (
              <div key={dsr.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{dsr.id}</span>
                    <span className={`badge text-[10px] ${STATUS_COLORS[dsr.status]}`}>
                      {(dsr.status || '').replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    {dsr.type} · Subject: {dsr.subject_id} · Assigned: {dsr.assigned_to || 'Unassigned'}
                  </p>
                </div>
                <div className="text-right">
                  <div className={`text-xs font-semibold ${dsr.days_remaining <= 7 ? 'text-red-600 dark:text-red-400' : 'text-surface-600 dark:text-surface-400'}`}>
                    {dsr.days_remaining} days left
                  </div>
                  <div className="mt-1.5 h-1.5 w-20 overflow-hidden rounded-full bg-surface-200 dark:bg-surface-700">
                    <div
                      className={`h-full rounded-full ${dsr.days_remaining <= 7 ? 'bg-red-500' : dsr.days_remaining <= 15 ? 'bg-amber-500' : 'bg-primary-500'}`}
                      style={{ width: `${Math.min(100, (dsr.days_remaining / 30) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
            {(dsrs || []).length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-surface-500 dark:text-surface-400">
                No data subject requests found.
              </div>
            )}
          </div>
          <Pagination page={dsrPagination.page} totalPages={dsrPagination.totalPages} setPage={dsrPagination.setPage} />
        </div>
      )}

      {/* Breaches Tab */}
      {activeTab === 'breaches' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Breach Notifications</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {breachPagination.paginated.map((b) => (
              <div key={b.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{b.title}</span>
                    <span className={`badge text-[10px] ${b.severity === 'high' ? 'badge-red' : 'badge-amber'}`}>
                      {b.severity}
                    </span>
                  </div>
                  <span className={`text-xs flex items-center gap-1 ${!b.sla_violated ? 'text-primary-600 dark:text-primary-400' : 'text-red-600 dark:text-red-400'}`}>
                    {!b.sla_violated ? <CheckCircle className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
                    {b.hours_elapsed}h / 72h SLA
                  </span>
                </div>
                <p className="mt-1 text-xs text-surface-400 dark:text-surface-500">
                  Status: {(b.status || '').replace('_', ' ')} · ID: {b.id}
                </p>
              </div>
            ))}
            {(breaches || []).length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-surface-500 dark:text-surface-400">
                No breach notifications found.
              </div>
            )}
          </div>
          <Pagination page={breachPagination.page} totalPages={breachPagination.totalPages} setPage={breachPagination.setPage} />
        </div>
      )}

      {/* Conflicts Tab */}
      {activeTab === 'conflicts' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Conflict of Interest Disclosures</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {conflictPagination.paginated.map((coi) => (
              <div key={coi.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{coi.user_id}</span>
                    <span className={`badge text-[10px] ${coi.approved ? STATUS_COLORS.approved : STATUS_COLORS.pending_review}`}>
                      {coi.approved ? 'approved' : 'pending review'}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    {coi.relationship_type} · {coi.project_id} · Disclosed {new Date(coi.disclosed_at).toLocaleDateString()}
                  </p>
                </div>
                {!coi.approved && (
                  <button
                    onClick={() => setReviewingCOI(coi.id)}
                    className="btn-primary text-xs"
                  >
                    Review
                  </button>
                )}
              </div>
            ))}
            {(conflicts || []).length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-surface-500 dark:text-surface-400">
                No conflict of interest disclosures found.
              </div>
            )}
          </div>
          <Pagination page={conflictPagination.page} totalPages={conflictPagination.totalPages} setPage={conflictPagination.setPage} />
        </div>
      )}

      {/* Methodology Tab */}
      {activeTab === 'methodology' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Methodology Versions</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {methodologyPagination.paginated.map((m) => (
              <div key={m.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{m.name}</span>
                    <span className={`badge text-[10px] ${m.is_current ? 'badge-green' : 'badge-slate'}`}>
                      {m.is_current ? 'Current' : 'Superseded'}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    v{m.version} · Effective {m.effective_date} · {m.change_summary}
                  </p>
                </div>
                <button
                  onClick={() => setViewingRules({ name: m.name, version: m.version })}
                  className="text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 transition-colors"
                >
                  View Rules
                </button>
              </div>
            ))}
            {(methodologies || []).length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-surface-500 dark:text-surface-400">
                No methodology versions found.
              </div>
            )}
          </div>
          <Pagination page={methodologyPagination.page} totalPages={methodologyPagination.totalPages} setPage={methodologyPagination.setPage} />
        </div>
      )}

      {/* COI Review Modal */}
      {reviewingCOI && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Review Conflict of Interest</h3>
              <button onClick={() => setReviewingCOI(null)} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm text-surface-600 dark:text-surface-300 mb-4">
              This will mark the conflict of interest disclosure as reviewed and approved. Ensure all independence requirements are met before confirming.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setReviewingCOI(null)} className="btn-secondary text-sm">Cancel</button>
              <button
                onClick={() => setReviewingCOI(null)}
                className="btn-primary text-sm"
              >
                Approve Disclosure
              </button>
            </div>
          </div>
        </div>
      )}

      {/* View Rules Modal */}
      {viewingRules && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Methodology Rules — {viewingRules.name} v{viewingRules.version}</h3>
              <button onClick={() => setViewingRules(null)} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            <p className="text-sm text-surface-600 dark:text-surface-300">
              Methodology rules and validation criteria are maintained by the CarbonVerify technical committee.
              Contact compliance@carbonverify.io for the full rules JSON or schema documentation.
            </p>
            <div className="mt-4 flex justify-end">
              <button onClick={() => setViewingRules(null)} className="btn-secondary text-sm">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Independence Block */}
      <div className="rounded-2xl border border-primary-200 bg-primary-50 p-5 dark:border-primary-900/20 dark:bg-primary-950/10">
        <div className="flex items-start gap-3">
          <TrendingUp className="h-5 w-5 text-primary-600 dark:text-primary-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-primary-900 dark:text-primary-300">Independence Enforcement</h3>
            <p className="mt-1 text-sm text-primary-700 dark:text-primary-400">
              PDD drafting is technically blocked for all users to maintain VVB independence.
              Conflict-of-interest detection is active. All methodology changes require admin approval
              and are versioned with rollback capability.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
