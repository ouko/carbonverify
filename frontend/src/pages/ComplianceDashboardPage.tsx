import { useState } from 'react'
import {
  Shield, FileText, AlertTriangle, CheckCircle, Clock,
  Users, Gavel, BookOpen, TrendingUp
} from 'lucide-react'

const MOCK_DSRS = [
  { id: 'DSR-001', type: 'access', subject: 'HH-4521', status: 'received', days_remaining: 28, assigned_to: 'Alice' },
  { id: 'DSR-002', type: 'erasure', subject: 'HH-3892', status: 'under_review', days_remaining: 15, assigned_to: 'Bob' },
  { id: 'DSR-003', type: 'portability', subject: 'DEV-104', status: 'fulfilled', days_remaining: 0, assigned_to: null },
]

const MOCK_BREACHES = [
  { id: 'B-001', title: 'Unauthorized photo access', severity: 'high', status: 'contained', hours_elapsed: 12, sla_ok: true },
  { id: 'B-002', title: 'Enumerator credential leak', severity: 'medium', status: 'notified_regulator', hours_elapsed: 48, sla_ok: true },
]

const MOCK_CONFLICTS = [
  { id: 'COI-001', user: 'Dr. Kimani', project: 'Project 12', type: 'financial', status: 'pending_review', disclosed: '2024-06-10' },
  { id: 'COI-002', user: 'Jane Wanjiku', project: 'Project 7', type: 'employment', status: 'approved', disclosed: '2024-05-22' },
]

const STATUS_COLORS: Record<string, string> = {
  received: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  under_review: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  fulfilled: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  rejected: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
  contained: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
  notified_regulator: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
  pending_review: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  approved: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
}

export function ComplianceDashboardPage() {
  const [activeTab, setActiveTab] = useState<'dsr' | 'breaches' | 'conflicts' | 'methodology'>('dsr')

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <Shield className="h-6 w-6 text-indigo-600" /> Compliance Center
        </h1>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Kenya Data Protection Act · VVB Independence
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Open DSRs</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">2</p>
          <p className="text-xs text-yellow-600">1 urgent (≤15 days)</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Active Breaches</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">1</p>
          <p className="text-xs text-green-600">Within 72h SLA</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Pending COI</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">1</p>
          <p className="text-xs text-gray-500">Awaiting review</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-green-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Methodologies</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">4</p>
          <p className="text-xs text-green-600">All current</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {[
          { key: 'dsr', label: 'Data Subject Requests', icon: FileText },
          { key: 'breaches', label: 'Breach Notifications', icon: AlertTriangle },
          { key: 'conflicts', label: 'Conflict of Interest', icon: Gavel },
          { key: 'methodology', label: 'Methodology Versions', icon: BookOpen },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                : 'text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* DSR Tab */}
      {activeTab === 'dsr' && (
        <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white">Data Subject Requests</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {MOCK_DSRS.map((dsr) => (
              <div key={dsr.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{dsr.id}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[dsr.status]}`}>
                      {dsr.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {dsr.type} · Subject: {dsr.subject} · Assigned: {dsr.assigned_to || 'Unassigned'}
                  </p>
                </div>
                <div className="text-right">
                  <div className={`text-xs font-medium ${dsr.days_remaining <= 7 ? 'text-red-600' : 'text-gray-600 dark:text-gray-400'}`}>
                    {dsr.days_remaining} days left
                  </div>
                  <div className="mt-1 h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className={`h-full rounded-full ${dsr.days_remaining <= 7 ? 'bg-red-500' : dsr.days_remaining <= 15 ? 'bg-yellow-500' : 'bg-green-500'}`}
                      style={{ width: `${Math.min(100, (dsr.days_remaining / 30) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Breaches Tab */}
      {activeTab === 'breaches' && (
        <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white">Breach Notifications</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {MOCK_BREACHES.map((b) => (
              <div key={b.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{b.title}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      b.severity === 'high' ? 'bg-red-100 text-red-800 dark:bg-red-900/30' : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30'
                    }`}>
                      {b.severity}
                    </span>
                  </div>
                  <span className={`text-xs ${b.sla_ok ? 'text-green-600' : 'text-red-600'}`}>
                    {b.sla_ok ? <CheckCircle className="inline h-3.5 w-3.5 mr-1" /> : <Clock className="inline h-3.5 w-3.5 mr-1" />}
                    {b.hours_elapsed}h / 72h SLA
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Status: {b.status} · ID: {b.id}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conflicts Tab */}
      {activeTab === 'conflicts' && (
        <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white">Conflict of Interest Disclosures</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {MOCK_CONFLICTS.map((coi) => (
              <div key={coi.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{coi.user}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[coi.status]}`}>
                      {coi.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {coi.type} · {coi.project} · Disclosed {coi.disclosed}
                  </p>
                </div>
                {coi.status === 'pending_review' && (
                  <button className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700">
                    Review
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Methodology Tab */}
      {activeTab === 'methodology' && (
        <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white">Methodology Versions</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {[
              { name: 'TPDDTEC v4', version: '4.2.1', effective: '2024-01-01', current: true, changes: 'Updated sample size requirement' },
              { name: 'VM0050', version: '2.0', effective: '2023-06-01', current: true, changes: 'Revised leakage factors' },
              { name: 'VMR0006', version: '1.1', effective: '2023-03-15', current: true, changes: 'Clarified monitoring boundaries' },
              { name: 'AMS-II.G', version: '3.0', effective: '2022-09-01', current: true, changes: 'Baseline recalculation protocol' },
            ].map((m, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{m.name}</span>
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-300">
                      {m.current ? 'Current' : 'Superseded'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    v{m.version} · Effective {m.effective} · {m.changes}
                  </p>
                </div>
                <button className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
                  View Rules
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Independence Block */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-900/20">
        <div className="flex items-start gap-3">
          <TrendingUp className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
          <div>
            <h3 className="font-medium text-indigo-900 dark:text-indigo-300">Independence Enforcement</h3>
            <p className="mt-1 text-sm text-indigo-700 dark:text-indigo-400">
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
