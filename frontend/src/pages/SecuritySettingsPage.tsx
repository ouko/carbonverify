import { useState } from 'react'
import { Shield, Smartphone, Key, Lock, Eye, EyeOff, CheckCircle, AlertTriangle } from 'lucide-react'

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
    // In production: call POST /auth/mfa/setup
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
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Security Settings</h1>

      {/* MFA Section */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center gap-3 mb-4">
          <Smartphone className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Multi-Factor Authentication</h2>
        </div>

        {mfaEnabled ? (
          <div className="flex items-center gap-3 rounded-lg bg-green-50 p-4 dark:bg-green-900/20">
            <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
            <div>
              <p className="font-medium text-green-800 dark:text-green-300">MFA is enabled</p>
              <p className="text-sm text-green-700 dark:text-green-400">Your account is protected with TOTP.</p>
            </div>
          </div>
        ) : mfaStep === 'setup' ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Add an extra layer of security by requiring a code from your authenticator app.
            </p>
            <button
              onClick={handleSetupMFA}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Set up MFA
            </button>
          </div>
        ) : mfaStep === 'confirm' ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Scan this QR code with Google Authenticator or Authy:
            </p>
            <div className="flex flex-col items-center gap-4 sm:flex-row">
              <img src={qrCode} alt="MFA QR Code" className="h-40 w-40 rounded-lg border border-gray-200 dark:border-gray-700" />
              <div className="space-y-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Or enter this secret manually:</p>
                <code className="rounded bg-gray-100 px-2 py-1 text-sm dark:bg-gray-700 dark:text-gray-300">{secret}</code>
              </div>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                maxLength={6}
                placeholder="Enter 6-digit code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
              <button
                onClick={handleConfirmMFA}
                disabled={totpCode.length !== 6}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Verify & Enable
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Password Section */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center gap-3 mb-4">
          <Key className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Change Password</h2>
        </div>
        <div className="space-y-3">
          <div className="relative">
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="Current password"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
            <button
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-2 top-2 text-gray-400"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <input
            type="password"
            placeholder="New password (min 12 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white"
          />
          <div className="flex gap-1 text-xs">
            <span className={password.length >= 12 ? 'text-green-600' : 'text-gray-400'}>● 12+ chars</span>
            <span className={/[A-Z]/.test(password) ? 'text-green-600' : 'text-gray-400'}>● Uppercase</span>
            <span className={/[0-9]/.test(password) ? 'text-green-600' : 'text-gray-400'}>● Number</span>
            <span className={/[^A-Za-z0-9]/.test(password) ? 'text-green-600' : 'text-gray-400'}>● Symbol</span>
          </div>
          <button className="rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600">
            Update Password
          </button>
        </div>
      </div>

      {/* Active Sessions */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Shield className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Active Sessions</h2>
          </div>
          <button
            onClick={() => setShowSessions(!showSessions)}
            className="text-sm text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
          >
            {showSessions ? 'Hide' : 'Show'}
          </button>
        </div>

        {showSessions && (
          <div className="space-y-3">
            {mockSessions.map((session) => (
              <div
                key={session.id}
                className={`flex items-center justify-between rounded-lg border p-3 ${
                  session.current
                    ? 'border-indigo-200 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-900/20'
                    : 'border-gray-200 dark:border-gray-700'
                }`}
              >
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {session.device} {session.current && <span className="text-xs text-indigo-600">(Current)</span>}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {session.ip} · {session.lastActive}
                  </p>
                </div>
                {!session.current && (
                  <button className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20">
                    Revoke
                  </button>
                )}
              </div>
            ))}
            <button className="mt-2 flex items-center gap-2 text-sm font-medium text-red-600 hover:text-red-700 dark:text-red-400">
              <Lock className="h-4 w-4" /> Log out all other sessions
            </button>
          </div>
        )}
      </div>

      {/* Security Alerts */}
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-6 dark:border-yellow-800 dark:bg-yellow-900/20">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          <div>
            <h3 className="font-medium text-yellow-800 dark:text-yellow-300">Security Recommendations</h3>
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-yellow-700 dark:text-yellow-400">
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
