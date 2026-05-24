import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import StatCard from '../components/StatCard';
import { useFieldData } from '../hooks/useFieldData';

export function FieldDashboardPage() {
  const navigate = useNavigate();
  const { stats, enumerators, loading } = useFieldData();
  const [filter, setFilter] = useState('');

  const filtered = enumerators.filter((e: any) =>
    e.name.toLowerCase().includes(filter.toLowerCase())
  );

  const alerts = filtered.filter((e: any) => e.rejectionRate > 15 || e.qualityScore < 80);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Field Operations</h1>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/field/enumerators')}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Manage Enumerators
          </button>
          <button
            onClick={() => navigate('/field/surveys')}
            className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-300 hover:bg-gray-50 dark:bg-gray-800 dark:text-gray-200 dark:ring-gray-700"
          >
            Survey Builder
          </button>
        </div>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 dark:border-orange-900 dark:bg-orange-900/20">
          <h3 className="mb-2 font-semibold text-orange-800 dark:text-orange-300">
            ⚠️ Data Quality Alerts ({alerts.length})
          </h3>
          <div className="space-y-1">
            {alerts.map((e: any) => (
              <p key={e.id} className="text-sm text-orange-700 dark:text-orange-400">
                {e.name}: {e.rejectionRate}% rejection rate — investigate
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Active Enumerators" value={stats.activeEnumerators} icon="👷" />
        <StatCard title="Surveys Today" value={stats.surveysToday} icon="📝" />
        <StatCard title="Photos Uploaded" value={stats.photosToday} icon="📸" />
        <StatCard title="Pending Sync" value={stats.pendingSync} icon="☁️" />
      </div>

      {/* Enumerator Table */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Enumerator Performance</h2>
            <input
              type="text"
              placeholder="Search..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Phone</th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Surveys</th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Quality</th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Reject %</th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Last Sync</th>
                <th className="px-6 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-800">
              {loading ? (
                <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-500">Loading...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-500">No enumerators found</td></tr>
              ) : (
                filtered.map((e: any) => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{e.name}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{e.phone}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900 dark:text-white">{e.surveys}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                      <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${e.qualityScore >= 90 ? 'bg-green-100 text-green-800' : e.qualityScore >= 75 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}`}>
                        {e.qualityScore}%
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-900 dark:text-white">{e.rejectionRate}%</td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm text-gray-500 dark:text-gray-400">{e.lastSync}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-center text-sm">
                      <span className={`inline-flex h-2.5 w-2.5 rounded-full ${e.lastSyncMinutes < 60 ? 'bg-green-500' : e.lastSyncMinutes < 240 ? 'bg-yellow-500' : 'bg-red-500'}`} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* WhatsApp Bot Status */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">WhatsApp Bot Status</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 p-6 sm:grid-cols-3">
          <div className="rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
            <p className="text-sm text-green-700 dark:text-green-300">Active Conversations</p>
            <p className="text-2xl font-bold text-green-900 dark:text-green-100">{stats.whatsappActive}</p>
          </div>
          <div className="rounded-lg bg-blue-50 p-4 dark:bg-blue-900/20">
            <p className="text-sm text-blue-700 dark:text-blue-300">Messages Today</p>
            <p className="text-2xl font-bold text-blue-900 dark:text-blue-100">{stats.whatsappMessages}</p>
          </div>
          <div className="rounded-lg bg-purple-50 p-4 dark:bg-purple-900/20">
            <p className="text-sm text-purple-700 dark:text-purple-300">Support Tickets</p>
            <p className="text-2xl font-bold text-purple-900 dark:text-purple-100">{stats.supportTickets}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
