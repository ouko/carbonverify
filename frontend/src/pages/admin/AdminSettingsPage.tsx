import { Settings, Shield, Info } from 'lucide-react'

export default function AdminSettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="page-title">Admin Settings</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
          System configuration and security policies
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/20 flex items-center justify-center">
              <Shield className="w-5 h-5 text-primary-500" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Security Policies</h3>
              <p className="text-xs text-surface-400 dark:text-surface-500">Password requirements, MFA enforcement, session policies</p>
            </div>
          </div>
          <div className="rounded-xl bg-surface-50 dark:bg-surface-800/40 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300">Minimum Password Length</p>
                <p className="text-[10px] text-surface-400 dark:text-surface-500">Enforced across all users</p>
              </div>
              <span className="text-sm font-bold text-surface-900 dark:text-surface-100">8 characters</span>
            </div>
            <div className="h-px bg-surface-200/60 dark:bg-surface-700/40" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300">MFA Required</p>
                <p className="text-[10px] text-surface-400 dark:text-surface-500">Multi-factor authentication</p>
              </div>
              <span className="text-sm font-bold text-surface-900 dark:text-surface-100">Optional</span>
            </div>
            <div className="h-px bg-surface-200/60 dark:bg-surface-700/40" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300">Session Timeout</p>
                <p className="text-[10px] text-surface-400 dark:text-surface-500">Inactive session expiry</p>
              </div>
              <span className="text-sm font-bold text-surface-900 dark:text-surface-100">24 hours</span>
            </div>
            <div className="h-px bg-surface-200/60 dark:bg-surface-700/40" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300">Max Failed Logins</p>
                <p className="text-[10px] text-surface-400 dark:text-surface-500">Account lockout threshold</p>
              </div>
              <span className="text-sm font-bold text-surface-900 dark:text-surface-100">5 attempts</span>
            </div>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
              <Settings className="w-5 h-5 text-surface-500" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">System Configuration</h3>
              <p className="text-xs text-surface-400 dark:text-surface-500">Platform-wide settings and defaults</p>
            </div>
          </div>
          <div className="rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/30 p-4">
            <div className="flex items-start gap-3">
              <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-amber-800 dark:text-amber-300">Coming Soon</p>
                <p className="text-[11px] text-amber-700 dark:text-amber-400 mt-1">
                  System configuration settings will be editable here in a future release. 
                  For now, contact your platform engineer to modify backend configuration.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
