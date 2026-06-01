import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Leaf, ArrowLeft, Mail, CheckCircle } from 'lucide-react'
import { api } from '../services/api'
import packageJson from '../../package.json'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email })
      setSuccess(true)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to send reset link'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-surface-50 dark:bg-surface-950">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary-500/5 blur-3xl animate-pulse-slow" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-primary-600/5 blur-3xl animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
      </div>

      <div className="relative w-full max-w-sm mx-4">
        <div className="glass-strong rounded-3xl p-8 shadow-soft-lg">
          <div className="flex flex-col items-center mb-8">
            <div className="relative mb-4">
              <div className="w-14 h-14 rounded-2xl bg-primary-500 flex items-center justify-center shadow-glow">
                <Leaf className="w-7 h-7 text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              CarbonVerify
            </h1>
            <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
              Reset your password
            </p>
          </div>

          {success ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <CheckCircle className="w-12 h-12 text-emerald-500" />
              </div>
              <p className="text-sm text-surface-700 dark:text-surface-300">
                If an account with that email exists, a reset link has been sent.
              </p>
              <p className="text-xs text-surface-400 dark:text-surface-500">
                Check your inbox and follow the instructions.
              </p>
              <button
                onClick={() => navigate('/login')}
                className="btn-primary w-full mt-4"
              >
                Back to Sign In
              </button>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-5 rounded-xl bg-red-50 border border-red-100 p-3.5 text-sm text-red-600 dark:bg-red-950/30 dark:border-red-900/30 dark:text-red-400 animate-slide-up">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                    Email address
                  </label>
                  <div className="relative">
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      placeholder="you@company.com"
                      className="input-modern pl-10"
                    />
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary w-full mt-2"
                >
                  {loading ? (
                    <div className="h-5 w-5 rounded-full border-[2.5px] border-white/30 border-t-white animate-spin" />
                  ) : (
                    'Send Reset Link'
                  )}
                </button>
              </form>

              <div className="mt-6 pt-5 border-t border-surface-100 dark:border-surface-800/50">
                <button
                  onClick={() => navigate('/login')}
                  className="flex items-center justify-center gap-1.5 text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors w-full"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Sign In
                </button>
              </div>
            </>
          )}
        </div>

        <div className="text-center mt-4">
          <span className="text-[10px] text-surface-300 dark:text-surface-700 font-medium tracking-wider uppercase">
            v{packageJson.version}
          </span>
        </div>
      </div>
    </div>
  )
}
