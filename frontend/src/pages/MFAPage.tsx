import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield, ArrowRight } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

export default function MFAPage() {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const verifyMFA = useAuthStore((s) => s.verifyMFA)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyMFA(code)
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Invalid verification code')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950">
      <div className="w-full max-w-sm mx-4">
        <div className="glass-strong rounded-3xl p-8 shadow-soft-lg">
          <div className="flex flex-col items-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-primary-500 flex items-center justify-center shadow-glow mb-4">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              Two-Factor Authentication
            </h1>
            <p className="text-sm text-surface-400 dark:text-surface-500 mt-1 text-center">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          {error && (
            <div className="mb-5 rounded-xl bg-red-50 border border-red-100 p-3.5 text-sm text-red-600 dark:bg-red-950/30 dark:border-red-900/30 dark:text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              id="totp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              maxLength={6}
              placeholder="000000"
              className="input-modern text-center text-2xl tracking-widest"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary group flex items-center justify-center gap-2"
            >
              {loading ? (
                <div className="h-5 w-5 rounded-full border-[2.5px] border-white/30 border-t-white animate-spin" />
              ) : (
                <>
                  Verify
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
