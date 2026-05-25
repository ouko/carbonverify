import { useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { Building2, Leaf, FileText, Download, Eye, Shield, ChevronRight } from 'lucide-react'

const MOCK_PORTFOLIO = {
  totalHeld: 12500,
  totalRetired: 8750,
  totalValue: 187500,
  vintageDistribution: [
    { year: 2022, tonnes: 2000 },
    { year: 2023, tonnes: 4500 },
    { year: 2024, tonnes: 6000 },
  ],
  methodologyBreakdown: [
    { name: 'TPDDTEC v4', value: 5500 },
    { name: 'VM0050', value: 4000 },
    { name: 'AMS-II.G', value: 3000 },
  ],
  projects: [
    { name: 'Kenya Clean Cookstoves', tonnes: 5000, retired: 3000, vintage: 2024, methodology: 'TPDDTEC v4', vvb: 'Verra' },
    { name: 'Ghana Biogas Program', tonnes: 4500, retired: 3500, vintage: 2023, methodology: 'VM0050', vvb: 'Gold Standard' },
    { name: 'Ethiopia LPG Adoption', tonnes: 3000, retired: 2250, vintage: 2024, methodology: 'AMS-II.G', vvb: 'Verra' },
  ],
}

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981']

export function CorporateDashboardPage() {
  const [activeTab, setActiveTab] = useState<'portfolio' | 'esg' | 'due-diligence'>('portfolio')

  const tabs = [
    { key: 'portfolio' as const, label: 'Portfolio' },
    { key: 'esg' as const, label: 'ESG Report' },
    { key: 'due-diligence' as const, label: 'Due Diligence' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
          <Building2 className="h-5 w-5 text-primary-600 dark:text-primary-400" />
        </div>
        <div>
          <h2 className="page-title">Corporate Buyer Dashboard</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500">Portfolio management and ESG reporting</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: 'Credits Held', value: MOCK_PORTFOLIO.totalHeld.toLocaleString(), sub: 'tCO₂e', icon: Leaf, color: 'text-primary-500' },
          { label: 'Retired', value: MOCK_PORTFOLIO.totalRetired.toLocaleString(), sub: 'tCO₂e', icon: Shield, color: 'text-primary-500' },
          { label: 'Portfolio Value', value: `$${MOCK_PORTFOLIO.totalValue.toLocaleString()}`, sub: '+12% YTD', icon: FileText, color: 'text-blue-500' },
          { label: 'Projects', value: MOCK_PORTFOLIO.projects.length.toString(), sub: 'Active', icon: Eye, color: 'text-violet-500' },
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
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
              activeTab === t.key
                ? 'bg-white dark:bg-surface-700 text-primary-700 dark:text-primary-300 shadow-sm'
                : 'text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'portfolio' && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Vintage Distribution</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={MOCK_PORTFOLIO.vintageDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.06} />
                  <XAxis dataKey="year" tick={{ fontSize: 12, fill: 'currentColor', opacity: 0.5 }} axisLine={false} tickLine={false} />
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
                  <Bar dataKey="tonnes" fill="#6366f1" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Methodology Breakdown</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={MOCK_PORTFOLIO.methodologyBreakdown}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {MOCK_PORTFOLIO.methodologyBreakdown.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
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
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-5 lg:col-span-2">
            <h3 className="mb-4 text-sm font-semibold text-surface-900 dark:text-surface-100">Project Contributions</h3>
            <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
              {MOCK_PORTFOLIO.projects.map((project) => (
                <div key={project.name} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{project.name}</p>
                    <p className="text-xs text-surface-400 dark:text-surface-500">
                      {project.methodology} · {project.vvb} · Vintage {project.vintage}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{project.tonnes.toLocaleString()} tCO₂e</p>
                    <p className="text-xs text-primary-600 dark:text-primary-400">{project.retired.toLocaleString()} retired</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'esg' && (
        <div className="mx-auto max-w-3xl space-y-5">
          <div className="card p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Generate ESG Offset Report</h3>
              <button className="btn-primary text-sm">
                <FileText className="h-4 w-4" /> Generate
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Company Name</label>
                <input className="input-modern" defaultValue="Acme Corporation" />
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Reporting Scope</label>
                <select className="input-modern">
                  <option>Scope 3</option>
                  <option>Scope 1 + 2</option>
                  <option>All Scopes</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Period Start</label>
                <input type="date" className="input-modern" defaultValue="2024-01-01" />
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Period End</label>
                <input type="date" className="input-modern" defaultValue="2024-12-31" />
              </div>
            </div>
          </div>

          <div className="card p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Latest Report</h3>
              <button className="text-sm font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 flex items-center gap-1.5 transition-colors">
                <Download className="h-4 w-4" /> Download PDF
              </button>
            </div>
            <div className="space-y-3">
              {[
                { label: 'Total Offsets Acquired', value: '12,500 tCO₂e' },
                { label: 'Total Retired', value: '8,750 tCO₂e' },
                { label: 'Net Position', value: '3,750 tCO₂e' },
              ].map((item) => (
                <div key={item.label} className="flex justify-between items-center py-2 border-b border-surface-100 dark:border-surface-800/50 last:border-0">
                  <span className="text-sm text-surface-600 dark:text-surface-400">{item.label}</span>
                  <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{item.value}</span>
                </div>
              ))}
              <div className="mt-3 rounded-xl bg-primary-50 dark:bg-primary-950/20 p-4">
                <p className="text-xs font-semibold text-primary-800 dark:text-primary-300 mb-2">SDG Impact</p>
                <div className="space-y-1.5">
                  {['SDG 7 — Affordable Clean Energy', 'SDG 13 — Climate Action', 'SDG 3 — Good Health & Wellbeing', 'SDG 15 — Life on Land'].map((sdg) => (
                    <p key={sdg} className="text-xs text-primary-700 dark:text-primary-400 flex items-center gap-1.5">
                      <ChevronRight className="h-3 w-3" /> {sdg}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'due-diligence' && (
        <div className="space-y-5">
          <div className="card p-5">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Due Diligence Packages</h3>
            <p className="mt-1 text-sm text-surface-400 dark:text-surface-500">
              Access underlying MRV data, VVB certificates, and project documentation for each token you hold.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {MOCK_PORTFOLIO.projects.map((project) => (
              <div key={project.name} className="card-hover p-5">
                <h4 className="font-semibold text-surface-900 dark:text-surface-100">{project.name}</h4>
                <p className="text-xs text-surface-400 dark:text-surface-500">{project.methodology} · {project.vvb}</p>
                <div className="mt-4 space-y-2">
                  {[
                    { label: 'VVB Certificate', icon: Download },
                    { label: 'MRV Calculation Report', icon: Download },
                    { label: 'Project PDD', icon: Download },
                    { label: 'Radix Token Provenance', icon: Eye },
                  ].map((doc) => (
                    <button key={doc.label} className="flex w-full items-center justify-between rounded-xl bg-surface-50 dark:bg-surface-800/50 px-4 py-2.5 text-sm text-surface-700 hover:bg-surface-100 dark:text-surface-300 dark:hover:bg-surface-800 transition-colors">
                      <span>{doc.label}</span>
                      <doc.icon className="h-4 w-4 text-surface-400" />
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
