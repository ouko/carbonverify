import { useState } from 'react';
import { Users, FileText, Camera, Cloud, MessageCircle, Search, AlertTriangle, Activity, Wrench, X } from 'lucide-react';
import StatCard from '../components/StatCard';
import { useFieldData } from '../hooks/useFieldData';

export function FieldDashboardPage() {
  const { stats, enumerators, loading } = useFieldData();
  const [filter, setFilter] = useState('');
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const filtered = enumerators.filter((e: any) =>
    e.name.toLowerCase().includes(filter.toLowerCase())
  );

  const alerts = filtered.filter((e: any) => e.rejectionRate > 15 || e.qualityScore < 80);

  return (
    <div className="space-y-6 relative">
      {toast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl bg-surface-900 text-white px-4 py-3 shadow-lg animate-slide-up">
          <Wrench className="h-4 w-4 text-primary-400" />
          <span className="text-sm">{toast}</span>
          <button onClick={() => setToast(null)} className="ml-2 text-surface-400 hover:text-white"><X className="h-3.5 w-3.5" /></button>
        </div>
      )}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">Field Operations</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">Monitor enumerators and field data collection</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => showToast('Enumerator management — coming in next release')} className="btn-primary text-sm">
            <Wrench className="w-3.5 h-3.5 mr-1" /> Manage Enumerators
          </button>
          <button onClick={() => showToast('Survey builder — coming in next release')} className="btn-secondary text-sm">
            Survey Builder
          </button>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900/30 dark:bg-amber-950/10">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <h3 className="font-semibold text-amber-800 dark:text-amber-300">Data Quality Alerts ({alerts.length})</h3>
          </div>
          <div className="space-y-1.5">
            {alerts.map((e: any) => (
              <p key={e.id} className="text-sm text-amber-700 dark:text-amber-400 flex items-center gap-2">
                <Activity className="h-3.5 w-3.5" />
                {e.name}: {e.rejectionRate}% rejection rate — investigate
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Active Enumerators" value={stats.activeEnumerators} icon={<Users className="h-5 w-5" />} color="emerald" />
        <StatCard title="Surveys Today" value={stats.surveysToday} icon={<FileText className="h-5 w-5" />} color="blue" />
        <StatCard title="Photos Uploaded" value={stats.photosToday} icon={<Camera className="h-5 w-5" />} color="violet" />
        <StatCard title="Pending Sync" value={stats.pendingSync} icon={<Cloud className="h-5 w-5" />} color="amber" />
      </div>

      {/* Enumerator Table */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Enumerator Performance</h3>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
              <input
                type="text"
                placeholder="Search..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="input-modern pl-9 py-2 text-sm"
              />
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Name</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Phone</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Surveys</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Quality</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Reject %</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Last Sync</th>
                <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
              {loading ? (
                <tr><td colSpan={7} className="px-6 py-8 text-center text-surface-400">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="px-6 py-8 text-center text-surface-400">No enumerators found</td></tr>
              ) : (
                filtered.map((e: any) => (
                  <tr key={e.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors">
                    <td className="px-6 py-4 font-semibold text-surface-900 dark:text-surface-100">{e.name}</td>
                    <td className="px-6 py-4 text-surface-500 dark:text-surface-400">{e.phone}</td>
                    <td className="px-6 py-4 text-right text-surface-900 dark:text-surface-100">{e.surveys}</td>
                    <td className="px-6 py-4 text-right">
                      <span className={`badge ${e.qualityScore >= 90 ? 'badge-green' : e.qualityScore >= 75 ? 'badge-amber' : 'badge-red'}`}>
                        {e.qualityScore}%
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right text-surface-900 dark:text-surface-100">{e.rejectionRate}%</td>
                    <td className="px-6 py-4 text-right text-surface-500 dark:text-surface-400">{e.lastSync}</td>
                    <td className="px-6 py-4 text-center">
                      <span className={`inline-flex h-2.5 w-2.5 rounded-full ${e.lastSyncMinutes < 60 ? 'bg-primary-500' : e.lastSyncMinutes < 240 ? 'bg-amber-500' : 'bg-red-500'}`} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* WhatsApp Bot Status */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">WhatsApp Bot Status</h3>
        </div>
        <div className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-3">
          <div className="rounded-xl bg-primary-50 dark:bg-primary-950/10 p-5">
            <div className="flex items-center gap-2 mb-2">
              <MessageCircle className="h-4 w-4 text-primary-500" />
              <span className="text-xs text-primary-600 dark:text-primary-400">Active Conversations</span>
            </div>
            <p className="text-2xl font-bold text-primary-900 dark:text-primary-100">{stats.whatsappActive}</p>
          </div>
          <div className="rounded-xl bg-blue-50 dark:bg-blue-950/10 p-5">
            <div className="flex items-center gap-2 mb-2">
              <MessageCircle className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-blue-600 dark:text-blue-400">Messages Today</span>
            </div>
            <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">{stats.whatsappMessages}</p>
          </div>
          <div className="rounded-xl bg-violet-50 dark:bg-violet-950/10 p-5">
            <div className="flex items-center gap-2 mb-2">
              <MessageCircle className="h-4 w-4 text-violet-500" />
              <span className="text-xs text-violet-600 dark:text-violet-400">Support Tickets</span>
            </div>
            <p className="text-2xl font-bold text-violet-900 dark:text-violet-100">{stats.supportTickets}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
