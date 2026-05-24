import { useState } from 'react'
import { Bell, Mail, MessageSquare, Smartphone, Save } from 'lucide-react'

export function SettingsPage() {
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

  const toggle = (key: keyof typeof settings) => {
    setSettings((s) => ({ ...s, [key]: !s[key] }))
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Notification Preferences</h2>

        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-gray-700">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Human Review Required</p>
              <p className="text-xs text-gray-500">When any agent queues an item for human review</p>
            </div>
            <button
              onClick={() => toggle('notifyHumanReview')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.notifyHumanReview ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.notifyHumanReview ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-gray-700">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">VVB Clarifications</p>
              <p className="text-xs text-gray-500">When a registry requests clarification</p>
            </div>
            <button
              onClick={() => toggle('notifyVVB')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.notifyVVB ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.notifyVVB ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-gray-700">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Calculation Anomalies</p>
              <p className="text-xs text-gray-500">Cross-project or statistical anomalies detected</p>
            </div>
            <button
              onClick={() => toggle('notifyAnomaly')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.notifyAnomaly ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.notifyAnomaly ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-gray-700">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Client Churn Risk</p>
              <p className="text-xs text-gray-500">When client success agent flags retention risk</p>
            </div>
            <button
              onClick={() => toggle('notifyChurn')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.notifyChurn ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.notifyChurn ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Deadline Warnings</p>
              <p className="text-xs text-gray-500">Upcoming SLA deadlines and overdue items</p>
            </div>
            <button
              onClick={() => toggle('notifyDeadline')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.notifyDeadline ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.notifyDeadline ? 'translate-x-5' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Notification Channels</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { key: 'channelEmail', icon: Mail, label: 'Email' },
            { key: 'channelInApp', icon: Bell, label: 'In-App' },
            { key: 'channelSMS', icon: Smartphone, label: 'SMS' },
            { key: 'channelWhatsApp', icon: MessageSquare, label: 'WhatsApp' },
          ].map((ch) => (
            <button
              key={ch.key}
              onClick={() => toggle(ch.key as any)}
              className={`flex flex-col items-center gap-2 rounded-lg border p-4 transition-colors ${
                (settings as any)[ch.key]
                  ? 'border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-900/20'
                  : 'border-gray-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/50'
              }`}
            >
              <ch.icon className={`h-6 w-6 ${(settings as any)[ch.key] ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400'}`} />
              <span className={`text-xs font-medium ${(settings as any)[ch.key] ? 'text-indigo-700 dark:text-indigo-300' : 'text-gray-600 dark:text-gray-400'}`}>
                {ch.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">Automation Settings</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Digest Mode</p>
              <p className="text-xs text-gray-500">Receive summaries instead of individual alerts</p>
            </div>
            <select
              value={settings.digestMode}
              onChange={(e) => setSettings((s) => ({ ...s, digestMode: e.target.value }))}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="realtime">Real-time</option>
              <option value="hourly">Hourly digest</option>
              <option value="daily">Daily digest</option>
            </select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Auto-Assign Queue Items</p>
              <p className="text-xs text-gray-500">Automatically assign items based on workload</p>
            </div>
            <button
              onClick={() => toggle('autoAssign')}
              className={`relative h-6 w-11 rounded-full transition-colors ${settings.autoAssign ? 'bg-indigo-600' : 'bg-gray-200 dark:bg-gray-700'}`}
            >
              <span className={`absolute left-1 top-1 h-4 w-4 rounded-full bg-white transition-transform ${settings.autoAssign ? 'translate-x-5' : ''}`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-white">Auto-Advance Threshold</p>
              <p className="text-xs text-gray-500">Minimum confidence for automatic state advancement</p>
            </div>
            <input
              type="number"
              min={0.5}
              max={1}
              step={0.01}
              value={settings.autoAdvanceThreshold}
              onChange={(e) => setSettings((s) => ({ ...s, autoAdvanceThreshold: parseFloat(e.target.value) }))}
              className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button className="flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-700">
          <Save className="h-4 w-4" /> Save Settings
        </button>
      </div>
    </div>
  )
}
