import { useState, useEffect } from 'react'
import { Bell, Mail, MessageSquare, Smartphone, Save, Loader2 } from 'lucide-react'
import { useUserSettings, useUpdateUserSettings } from '../../hooks/useSecurity'

export function SettingsPage() {
  const { data: apiSettings, isLoading, isError } = useUserSettings()
  const updateSettings = useUpdateUserSettings()

  const [settings, setSettings] = useState({
    notifyHumanReview: true,
    notifyVVB: true,
    notifyAnomaly: true,
    notifyChurn: true,
    notifyDeadline: true,
    channelEmail: true,
    channelInApp: true,
    channelSMS: false,
    channelWhatsApp: false,
    digestMode: 'daily',
    autoAssign: false,
    autoAdvanceThreshold: 0.95,
  })

  useEffect(() => {
    if (apiSettings) {
      setSettings(apiSettings)
    }
  }, [apiSettings])

  const toggle = (key: keyof typeof settings) => {
    setSettings((s) => ({ ...s, [key]: !s[key] }))
  }

  const handleSave = () => {
    updateSettings.mutate(settings)
  }

  const toggleRow = (label: string, desc: string, key: keyof typeof settings) => (
    <div className="flex items-center justify-between py-3 border-b border-surface-100 dark:border-surface-800/50 last:border-0">
      <div>
        <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{label}</p>
        <p className="text-xs text-surface-400 dark:text-surface-500 mt-0.5">{desc}</p>
      </div>
      <button
        onClick={() => toggle(key)}
        className={`relative h-6 w-11 rounded-full transition-colors ${settings[key] ? 'bg-primary-600' : 'bg-surface-200 dark:bg-surface-700'}`}
      >
        <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings[key] ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  )

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="mx-auto max-w-3xl card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">Failed to load settings</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="page-title">Settings</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">Configure notification and automation preferences</p>
      </div>

      <div className="card p-6">
        <h3 className="mb-4 font-semibold text-surface-900 dark:text-surface-100">Notification Preferences</h3>
        <div className="space-y-0">
          {toggleRow('Human Review Required', 'When any agent queues an item for human review', 'notifyHumanReview')}
          {toggleRow('VVB Clarifications', 'When a registry requests clarification', 'notifyVVB')}
          {toggleRow('Calculation Anomalies', 'Cross-project or statistical anomalies detected', 'notifyAnomaly')}
          {toggleRow('Client Churn Risk', 'When client success agent flags retention risk', 'notifyChurn')}
          {toggleRow('Deadline Warnings', 'Upcoming SLA deadlines and overdue items', 'notifyDeadline')}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="mb-4 font-semibold text-surface-900 dark:text-surface-100">Notification Channels</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { key: 'channelEmail' as const, icon: Mail, label: 'Email' },
            { key: 'channelInApp' as const, icon: Bell, label: 'In-App' },
            { key: 'channelSMS' as const, icon: Smartphone, label: 'SMS' },
            { key: 'channelWhatsApp' as const, icon: MessageSquare, label: 'WhatsApp' },
          ].map((ch) => (
            <button
              key={ch.key}
              onClick={() => toggle(ch.key)}
              className={`flex flex-col items-center gap-2 rounded-xl border p-4 transition-all ${
                (settings as any)[ch.key]
                  ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10'
                  : 'border-surface-200 hover:bg-surface-50 dark:border-surface-700 dark:hover:bg-surface-800/50'
              }`}
            >
              <ch.icon className={`h-6 w-6 ${(settings as any)[ch.key] ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400'}`} />
              <span className={`text-xs font-medium ${(settings as any)[ch.key] ? 'text-primary-700 dark:text-primary-300' : 'text-surface-600 dark:text-surface-400'}`}>
                {ch.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h3 className="mb-4 font-semibold text-surface-900 dark:text-surface-100">Automation Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">Digest Mode</p>
              <p className="text-xs text-surface-400 dark:text-surface-500">Receive summaries instead of individual alerts</p>
            </div>
            <select
              value={settings.digestMode}
              onChange={(e) => setSettings((s) => ({ ...s, digestMode: e.target.value }))}
              className="input-modern py-1.5 px-3 text-sm appearance-none cursor-pointer"
            >
              <option value="realtime">Real-time</option>
              <option value="hourly">Hourly digest</option>
              <option value="daily">Daily digest</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">Auto-Assign Queue Items</p>
              <p className="text-xs text-surface-400 dark:text-surface-500">Automatically assign items based on workload</p>
            </div>
            <button
              onClick={() => toggle('autoAssign')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.autoAssign ? 'bg-primary-600' : 'bg-surface-200 dark:bg-surface-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.autoAssign ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">Auto-Advance Threshold</p>
              <p className="text-xs text-surface-400 dark:text-surface-500">Minimum confidence for automatic state advancement</p>
            </div>
            <input
              type="number"
              min={0.5}
              max={1}
              step={0.01}
              value={settings.autoAdvanceThreshold}
              onChange={(e) => setSettings((s) => ({ ...s, autoAdvanceThreshold: parseFloat(e.target.value) }))}
              className="w-24 input-modern py-1.5 px-2 text-sm text-center"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={updateSettings.isPending}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {updateSettings.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save Settings
        </button>
      </div>
    </div>
  )
}
