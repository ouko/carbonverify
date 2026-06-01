import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Leaf, Eye, EyeOff, CheckCircle, Lock, ArrowRight } from 'lucide-react'
import { api } from '../services/api'
import packageJson from '../../package.json'

function validatePassword(password: string): string | null {
  if (password.length < 12) return 'Password must be at least 12 characters'
  if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter'
  if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter'
  if (!/\d/.test(password)) return 'Password must contain at least one digit'
  if (!/[@$!%*?&]/.test(password)) return 'Password must contain at least one special character (@$!%*?&)'
  return null
}

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const navigate = useNavigate()

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing reset token. Please request a new password reset.')
    }
  }, [token])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)

    const validationError = validatePassword(password)
    if (validationError) {
      setError(validationError)
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, new_password: password })
      setSuccess(true)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to reset password'
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
              Create a new password
            </p>
          </div>

          {success ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <CheckCircle className="w-12 h-12 text-emerald-500" />
              </div>
              <p className="text-sm text-surface-700 dark:text-surface-300">
                Your password has been reset successfully.
              </p>
              <button
                onClick={() => navigate('/login')}
                className="btn-primary w-full mt-4 flex items-center justify-center gap-2"
              >
                Sign In
                <ArrowRight className="w-4 h-4" />
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
                  <label htmlFor="password" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      disabled={!token}
                      placeholder="••••••••"
                      className="input-modern pr-11 pl-10"
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="confirmPassword" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                    <input
                      id="confirmPassword"
                      type={showConfirm ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      disabled={!token}
                      placeholder="••••••••"
                      className="input-modern pr-11 pl-10"
                    />
                    <button
                      type="button"
                      aria-label={showConfirm ? 'Hide password' : 'Show password'}
                      onClick={() => setShowConfirm(!showConfirm)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors"
                    >
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading || !token}
                  className="btn-primary w-full mt-2 group"
                >
                  {loading ? (
                    <div className="h-5 w-5 rounded-full border-[2.5px] border-white/30 border-t-white animate-spin" />
                  ) : (
                    <>
                      Reset Password
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                    </>
                  )}
                </button>
              </form>
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
