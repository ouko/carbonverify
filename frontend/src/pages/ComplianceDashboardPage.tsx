import { useState } from 'react'
import {
  Shield, FileText, AlertTriangle, CheckCircle, Clock,
  Users, Gavel, BookOpen, TrendingUp
} from 'lucide-react'
import { useDSRs, useBreaches, useConflicts } from '../hooks/useCompliance'
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

export function ComplianceDashboardPage() {
  const [activeTab, setActiveTab] = useState<'dsr' | 'breaches' | 'conflicts' | 'methodology'>('dsr')

  const { data: dsrs, isLoading: dsrsLoading, isError: dsrsError } = useDSRs()
  const { data: breaches, isLoading: breachesLoading, isError: breachesError } = useBreaches()
  const { data: conflicts, isLoading: conflictsLoading, isError: conflictsError } = useConflicts()

  const isLoading = dsrsLoading || breachesLoading || conflictsLoading
  const isError = dsrsError || breachesError || conflictsError

  const openDSRs = (dsrs || []).filter(d => d.status !== 'fulfilled' && d.status !== 'rejected').length
  const urgentDSRs = (dsrs || []).filter(d => d.days_remaining <= 15 && d.status !== 'fulfilled' && d.status !== 'rejected').length
  const activeBreaches = (breaches || []).filter(b => b.status !== 'resolved').length
  const slaOkBreaches = (breaches || []).filter(b => b.sla_ok).length
  const pendingCOI = (conflicts || []).filter(c => c.status === 'pending_review').length

  const tabs = [
    { key: 'dsr' as const, label: 'Data Subject Requests', icon: FileText },
    { key: 'breaches' as const, label: 'Breach Notifications', icon: AlertTriangle },
    { key: 'conflicts' as const, label: 'Conflict of Interest', icon: Gavel },
    { key: 'methodology' as const, label: 'Methodology Versions', icon: BookOpen },
  ]

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
          { label: 'Methodologies', value: '4', sub: 'All current', icon: BookOpen, color: 'text-primary-500' },
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
            {(dsrs || []).map((dsr) => (
              <div key={dsr.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{dsr.id}</span>
                    <span className={`badge text-[10px] ${STATUS_COLORS[dsr.status]}`}>
                      {(dsr.status || '').replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    {dsr.type} · Subject: {dsr.subject} · Assigned: {dsr.assigned_to || 'Unassigned'}
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
        </div>
      )}

      {/* Breaches Tab */}
      {activeTab === 'breaches' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Breach Notifications</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {(breaches || []).map((b) => (
              <div key={b.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{b.title}</span>
                    <span className={`badge text-[10px] ${b.severity === 'high' ? 'badge-red' : 'badge-amber'}`}>
                      {b.severity}
                    </span>
                  </div>
                  <span className={`text-xs flex items-center gap-1 ${b.sla_ok ? 'text-primary-600 dark:text-primary-400' : 'text-red-600 dark:text-red-400'}`}>
                    {b.sla_ok ? <CheckCircle className="h-3.5 w-3.5" /> : <Clock className="h-3.5 w-3.5" />}
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
        </div>
      )}

      {/* Conflicts Tab */}
      {activeTab === 'conflicts' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Conflict of Interest Disclosures</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {(conflicts || []).map((coi) => (
              <div key={coi.id} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{coi.user}</span>
                    <span className={`badge text-[10px] ${STATUS_COLORS[coi.status]}`}>
                      {(coi.status || '').replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    {coi.type} · {coi.project} · Disclosed {coi.disclosed}
                  </p>
                </div>
                {coi.status === 'pending_review' && (
                  <button
                    onClick={() => alert('Conflict of interest review workflow coming soon')}
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
        </div>
      )}

      {/* Methodology Tab */}
      {activeTab === 'methodology' && (
        <div className="card overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Methodology Versions</h3>
          </div>
          <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
            {[
              { name: 'TPDDTEC v4', version: '4.2.1', effective: '2024-01-01', current: true, changes: 'Updated sample size requirement' },
              { name: 'VM0050', version: '2.0', effective: '2023-06-01', current: true, changes: 'Revised leakage factors' },
              { name: 'VMR0006', version: '1.1', effective: '2023-03-15', current: true, changes: 'Clarified monitoring boundaries' },
              { name: 'AMS-II.G', version: '3.0', effective: '2022-09-01', current: true, changes: 'Baseline recalculation protocol' },
            ].map((m, i) => (
              <div key={i} className="flex items-center justify-between px-6 py-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{m.name}</span>
                    <span className="badge badge-green text-[10px]">
                      {m.current ? 'Current' : 'Superseded'}
                    </span>
                  </div>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                    v{m.version} · Effective {m.effective} · {m.changes}
                  </p>
                </div>
                <button
                  onClick={() => window.alert(`View rules for ${m.name} v${m.version}`)}
                  className="text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 transition-colors"
                >
                  View Rules
                </button>
              </div>
            ))}
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
