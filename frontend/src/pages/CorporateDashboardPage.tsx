import { useState } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { Building2, Leaf, FileText, Download, Eye, Shield } from 'lucide-react'

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

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
        <Building2 className="h-6 w-6 text-indigo-600" /> Corporate Buyer Dashboard
      </h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <Leaf className="h-5 w-5 text-green-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Credits Held</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{MOCK_PORTFOLIO.totalHeld.toLocaleString()}</p>
          <p className="text-xs text-gray-500">tCO₂e</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-indigo-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Retired</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{MOCK_PORTFOLIO.totalRetired.toLocaleString()}</p>
          <p className="text-xs text-gray-500">tCO₂e</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Portfolio Value</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">${MOCK_PORTFOLIO.totalValue.toLocaleString()}</p>
          <p className="text-xs text-green-600">+12% YTD</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-purple-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Projects</span>
          </div>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{MOCK_PORTFOLIO.projects.length}</p>
          <p className="text-xs text-gray-500">Active</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {[
          { key: 'portfolio', label: 'Portfolio' },
          { key: 'esg', label: 'ESG Report' },
          { key: 'due-diligence', label: 'Due Diligence' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key as any)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === t.key
                ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                : 'text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'portfolio' && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Vintage Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={MOCK_PORTFOLIO.vintageDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="tonnes" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Methodology Breakdown</h3>
            <ResponsiveContainer width="100%" height={250}>
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
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 lg:col-span-2">
            <h3 className="mb-4 text-sm font-semibold text-gray-800 dark:text-white">Project Contributions</h3>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {MOCK_PORTFOLIO.projects.map((project) => (
                <div key={project.name} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{project.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {project.methodology} · {project.vvb} · Vintage {project.vintage}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{project.tonnes.toLocaleString()} tCO₂e</p>
                    <p className="text-xs text-green-600">{project.retired.toLocaleString()} retired</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'esg' && (
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">Generate ESG Offset Report</h3>
              <button className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                <FileText className="h-4 w-4" /> Generate
              </button>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Company Name</label>
                <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" defaultValue="Acme Corporation" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Reporting Scope</label>
                <select className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                  <option>Scope 3</option>
                  <option>Scope 1 + 2</option>
                  <option>All Scopes</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Period Start</label>
                <input type="date" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" defaultValue="2024-01-01" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Period End</label>
                <input type="date" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" defaultValue="2024-12-31" />
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 dark:text-white">Latest Report</h3>
              <button className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
                <Download className="h-4 w-4" /> Download PDF
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
                <span className="text-sm text-gray-600 dark:text-gray-400">Total Offsets Acquired</span>
                <span className="text-sm font-medium text-gray-900 dark:text-white">12,500 tCO₂e</span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
                <span className="text-sm text-gray-600 dark:text-gray-400">Total Retired</span>
                <span className="text-sm font-medium text-gray-900 dark:text-white">8,750 tCO₂e</span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
                <span className="text-sm text-gray-600 dark:text-gray-400">Net Position</span>
                <span className="text-sm font-medium text-gray-900 dark:text-white">3,750 tCO₂e</span>
              </div>
              <div className="rounded-lg bg-green-50 p-3 dark:bg-green-900/20">
                <p className="text-xs font-medium text-green-800 dark:text-green-300">SDG Impact</p>
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-green-700 dark:text-green-400">SDG 7 — Affordable Clean Energy</p>
                  <p className="text-xs text-green-700 dark:text-green-400">SDG 13 — Climate Action</p>
                  <p className="text-xs text-green-700 dark:text-gray-400">SDG 3 — Good Health & Wellbeing</p>
                  <p className="text-xs text-green-700 dark:text-gray-400">SDG 15 — Life on Land</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'due-diligence' && (
        <div className="space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 className="font-semibold text-gray-900 dark:text-white">Due Diligence Packages</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Access underlying MRV data, VVB certificates, and project documentation for each token you hold.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {MOCK_PORTFOLIO.projects.map((project) => (
              <div key={project.name} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                <h4 className="font-medium text-gray-900 dark:text-white">{project.name}</h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">{project.methodology} · {project.vvb}</p>
                <div className="mt-3 space-y-2">
                  <button className="flex w-full items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">
                    <span>VVB Certificate</span>
                    <Download className="h-4 w-4" />
                  </button>
                  <button className="flex w-full items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">
                    <span>MRV Calculation Report</span>
                    <Download className="h-4 w-4" />
                  </button>
                  <button className="flex w-full items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">
                    <span>Project PDD</span>
                    <Download className="h-4 w-4" />
                  </button>
                  <button className="flex w-full items-center justify-between rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600">
                    <span>Radix Token Provenance</span>
                    <Eye className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
