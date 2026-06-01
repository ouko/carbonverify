import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Leaf, Eye, EyeOff, ArrowRight, Shield } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import packageJson from '../../package.json'

function OAuthButton({
  provider,
  label,
  onClick,
}: {
  provider: 'google' | 'microsoft' | 'okta'
  label: string
  onClick: () => void
}) {
  const colors: Record<string, string> = {
    google: 'bg-white text-surface-800 border border-surface-200 hover:bg-surface-50 dark:bg-surface-900 dark:text-surface-200 dark:border-surface-700 dark:hover:bg-surface-800',
    microsoft: 'bg-white text-surface-800 border border-surface-200 hover:bg-surface-50 dark:bg-surface-900 dark:text-surface-200 dark:border-surface-700 dark:hover:bg-surface-800',
    okta: 'bg-white text-surface-800 border border-surface-200 hover:bg-surface-50 dark:bg-surface-900 dark:text-surface-200 dark:border-surface-700 dark:hover:bg-surface-800',
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center justify-center gap-2.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${colors[provider]}`}
    >
      <span className="text-base">
        {provider === 'google' && '🔍'}
        {provider === 'microsoft' && '⊞'}
        {provider === 'okta' && '◉'}
      </span>
      {label}
    </button>
  )
}

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err: any) {
      // Show actual API error message if available
      const msg = err?.response?.data?.detail || err?.message || 'Invalid email or password'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-surface-50 dark:bg-surface-950">
      {/* Animated background shapes */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary-500/5 blur-3xl animate-pulse-slow" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-primary-600/5 blur-3xl animate-pulse-slow" style={{ animationDelay: '1.5s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-primary-400/3 blur-3xl" />
      </div>

      {/* Grid pattern overlay */}
      <div 
        className="absolute inset-0 opacity-[0.015] dark:opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23059669' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }}
      />

      <div className="relative w-full max-w-sm mx-4">
        {/* Card */}
        <div className="glass-strong rounded-3xl p-8 shadow-soft-lg">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="relative mb-4">
              <div className="w-14 h-14 rounded-2xl bg-primary-500 flex items-center justify-center shadow-glow">
                <Leaf className="w-7 h-7 text-white" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-surface-100 dark:bg-surface-800 flex items-center justify-center">
                <Shield className="w-3 h-3 text-primary-500" />
              </div>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              CarbonVerify
            </h1>
            <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
              Carbon Credit MRV Platform
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-5 rounded-xl bg-red-50 border border-red-100 p-3.5 text-sm text-red-600 dark:bg-red-950/30 dark:border-red-900/30 dark:text-red-400 animate-slide-up">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="input-modern"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="input-modern pr-11"
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

            <div className="flex items-center justify-between">
              <button
                type="submit"
                disabled={loading}
                className="btn-primary group"
              >
                {loading ? (
                  <div className="h-5 w-5 rounded-full border-[2.5px] border-white/30 border-t-white animate-spin" />
                ) : (
                  <>
                    Sign In
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => navigate('/forgot-password')}
                className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors"
              >
                Forgot password?
              </button>
            </div>
          </form>

          {/* OAuth */}
          <div className="mt-5 space-y-3">
            <div className="relative flex items-center gap-3">
              <div className="h-px flex-1 bg-surface-100 dark:bg-surface-800/50" />
              <span className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 font-medium">Or continue with</span>
              <div className="h-px flex-1 bg-surface-100 dark:bg-surface-800/50" />
            </div>
            <div className="space-y-2">
              <OAuthButton provider="google" label="Google" onClick={() => window.location.href = '/auth/oauth/google'} />
              <OAuthButton provider="microsoft" label="Microsoft" onClick={() => window.location.href = '/auth/oauth/microsoft'} />
              <OAuthButton provider="okta" label="Okta" onClick={() => window.location.href = '/auth/oauth/okta'} />
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 pt-5 border-t border-surface-100 dark:border-surface-800/50">
            <p className="text-center text-xs text-surface-400 dark:text-surface-500">
              Protected by multi-factor authentication and blockchain audit trails
            </p>
          </div>
        </div>

        {/* Version badge */}
        <div className="text-center mt-4">
          <span className="text-[10px] text-surface-300 dark:text-surface-700 font-medium tracking-wider uppercase">
            v{packageJson.version}
          </span>
        </div>
      </div>
    </div>
  )
}
