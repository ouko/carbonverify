import { useState } from 'react'
import { Shield, Smartphone, Key, Eye, EyeOff, CheckCircle, AlertTriangle, LogOut, ChevronDown, ChevronUp } from 'lucide-react'

export function SecuritySettingsPage() {
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [mfaStep, setMfaStep] = useState<'setup' | 'confirm' | 'done'>('setup')
  const [qrCode, setQrCode] = useState('')
  const [secret, setSecret] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [showSessions, setShowSessions] = useState(false)
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const mockSessions = [
    { id: 'sess-1', device: 'Chrome on macOS', ip: '192.168.1.1', lastActive: '2 mins ago', current: true },
    { id: 'sess-2', device: 'Safari on iPhone', ip: '10.0.0.5', lastActive: '3 hours ago', current: false },
  ]

  const handleSetupMFA = async () => {
    setQrCode('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
    setSecret('JBSWY3DPEHPK3PXP')
    setMfaStep('confirm')
  }

  const handleConfirmMFA = async () => {
    if (totpCode.length === 6) {
      setMfaEnabled(true)
      setMfaStep('done')
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="page-title">Security Settings</h2>
        <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
          Manage authentication and account security
        </p>
      </div>

      {/* MFA Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
            <Smartphone className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Multi-Factor Authentication</h3>
            <p className="text-xs text-surface-400 dark:text-surface-500">Add an extra layer of security</p>
          </div>
        </div>

        {mfaEnabled ? (
          <div className="flex items-center gap-3 rounded-xl bg-primary-50 dark:bg-primary-950/20 p-4">
            <CheckCircle className="h-5 w-5 text-primary-600 dark:text-primary-400 shrink-0" />
            <div>
              <p className="font-semibold text-primary-800 dark:text-primary-300">MFA is enabled</p>
              <p className="text-sm text-primary-600 dark:text-primary-400">Your account is protected with TOTP.</p>
            </div>
          </div>
        ) : mfaStep === 'setup' ? (
          <div className="space-y-4">
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Add an extra layer of security by requiring a code from your authenticator app.
            </p>
            <button onClick={handleSetupMFA} className="btn-primary">
              Set up MFA
            </button>
          </div>
        ) : mfaStep === 'confirm' ? (
          <div className="space-y-5">
            <p className="text-sm text-surface-500 dark:text-surface-400">
              Scan this QR code with Google Authenticator or Authy:
            </p>
            <div className="flex flex-col items-center gap-5 sm:flex-row">
              <img src={qrCode} alt="MFA QR Code" className="h-40 w-40 rounded-xl border border-surface-200 dark:border-surface-700" />
              <div className="space-y-2">
                <p className="text-xs text-surface-400 dark:text-surface-500">Or enter this secret manually:</p>
                <code className="block rounded-xl bg-surface-100 dark:bg-surface-800 px-3 py-2 text-sm font-mono text-surface-700 dark:text-surface-300">{secret}</code>
              </div>
            </div>
            <div className="flex gap-2 max-w-xs">
              <input
                type="text"
                maxLength={6}
                placeholder="Enter 6-digit code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                className="input-modern text-center tracking-[0.3em] font-mono text-lg"
              />
              <button
                onClick={handleConfirmMFA}
                disabled={totpCode.length !== 6}
                className="btn-primary whitespace-nowrap disabled:opacity-50"
              >
                Verify
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Password Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
            <Key className="h-5 w-5 text-surface-600 dark:text-surface-400" />
          </div>
          <div>
            <h3 className="font-semibold text-surface-900 dark:text-surface-100">Change Password</h3>
            <p className="text-xs text-surface-400 dark:text-surface-500">Update your account password</p>
          </div>
        </div>
        <div className="space-y-4 max-w-md">
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="Current password"
              className="input-modern pr-11"
            />
            <button
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <input
            type="password"
            placeholder="New password (min 12 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input-modern"
          />
          <div className="flex flex-wrap gap-2 text-xs">
            <span className={`flex items-center gap-1 ${password.length >= 12 ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400 dark:text-surface-500'}`}>
              <span className="w-1 h-1 rounded-full bg-current" /> 12+ chars
            </span>
            <span className={`flex items-center gap-1 ${/[A-Z]/.test(password) ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400 dark:text-surface-500'}`}>
              <span className="w-1 h-1 rounded-full bg-current" /> Uppercase
            </span>
            <span className={`flex items-center gap-1 ${/[0-9]/.test(password) ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400 dark:text-surface-500'}`}>
              <span className="w-1 h-1 rounded-full bg-current" /> Number
            </span>
            <span className={`flex items-center gap-1 ${/[^A-Za-z0-9]/.test(password) ? 'text-primary-600 dark:text-primary-400' : 'text-surface-400 dark:text-surface-500'}`}>
              <span className="w-1 h-1 rounded-full bg-current" /> Symbol
            </span>
          </div>
          <button className="btn-primary text-sm">
            Update Password
          </button>
        </div>
      </div>

      {/* Active Sessions */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
              <Shield className="h-5 w-5 text-surface-600 dark:text-surface-400" />
            </div>
            <div>
              <h3 className="font-semibold text-surface-900 dark:text-surface-100">Active Sessions</h3>
              <p className="text-xs text-surface-400 dark:text-surface-500">Manage your active login sessions</p>
            </div>
          </div>
          <button
            onClick={() => setShowSessions(!showSessions)}
            className="btn-ghost text-xs"
          >
            {showSessions ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {showSessions && (
          <div className="space-y-3">
            {mockSessions.map((session) => (
              <div
                key={session.id}
                className={`flex items-center justify-between rounded-xl border p-4 ${
                  session.current
                    ? 'border-primary-200 bg-primary-50/50 dark:border-primary-800/30 dark:bg-primary-950/10'
                    : 'border-surface-200 dark:border-surface-700'
                }`}
              >
                <div>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">
                    {session.device} {session.current && <span className="text-xs text-primary-600 dark:text-primary-400 font-medium ml-1">(Current)</span>}
                  </p>
                  <p className="text-xs text-surface-400 dark:text-surface-500">
                    {session.ip} · {session.lastActive}
                  </p>
                </div>
                {!session.current && (
                  <button className="text-xs font-medium text-red-600 hover:text-red-700 dark:text-red-400 px-2 py-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors">
                    Revoke
                  </button>
                )}
              </div>
            ))}
            <button className="flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 dark:text-red-400 transition-colors">
              <LogOut className="h-4 w-4" /> Log out all other sessions
            </button>
          </div>
        )}
      </div>

      {/* Security Alerts */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900/30 dark:bg-amber-950/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-amber-800 dark:text-amber-300">Security Recommendations</h3>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-amber-700 dark:text-amber-400">
              <li>Enable MFA if you haven't already</li>
              <li>Use a unique password not shared with other services</li>
              <li>Review active sessions regularly and revoke unused ones</li>
              <li>Report suspicious activity immediately</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
