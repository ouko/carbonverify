import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

export default function InviteAcceptPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('invite');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    // If user is already logged in, redirect to dashboard
    const state = useAuthStore.getState();
    if (state.user) {
      navigate('/');
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('Invite token is missing from the URL.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (!name.trim()) {
      setError('Please enter your full name.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/invite/accept', {
        token,
        password,
        name,
      });
      setSuccess(true);
      // Redirect to login so user can authenticate with their new account
      setTimeout(() => navigate('/login'), 2500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to accept invite. Please check your token and try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950">
        <div className="max-w-md w-full mx-4 p-8 bg-white dark:bg-surface-900 rounded-2xl shadow-sm border border-surface-100 dark:border-surface-800 text-center">
          <AlertCircle className="w-12 h-12 text-rose-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">Invalid Invite Link</h1>
          <p className="text-surface-500 dark:text-surface-400">The invite token is missing. Please ask your administrator for a valid invite link.</p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950">
        <div className="max-w-md w-full mx-4 p-8 bg-white dark:bg-surface-900 rounded-2xl shadow-sm border border-surface-100 dark:border-surface-800 text-center">
          <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-surface-900 dark:text-surface-100 mb-2">Account Created!</h1>
          <p className="text-surface-500 dark:text-surface-400">Your account has been created. Redirecting you to sign in...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950">
      <div className="max-w-md w-full mx-4 p-8 bg-white dark:bg-surface-900 rounded-2xl shadow-sm border border-surface-100 dark:border-surface-800">
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100 mb-1">Accept Invite</h1>
        <p className="text-sm text-surface-500 dark:text-surface-400 mb-6">
          Create your account to join the CarbonVerify platform.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800/30 text-rose-700 dark:text-rose-300 text-sm flex items-start gap-2">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Full Name
            </label>
            <input
              id="name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input-modern w-full"
              placeholder="Your full name"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-modern w-full"
              placeholder="Min 8 characters"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="input-modern w-full"
              placeholder="Re-enter password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating account...
              </>
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-surface-400 dark:text-surface-500">
          Already have an account?{' '}
          <button onClick={() => navigate('/login')} className="text-primary-600 dark:text-primary-400 hover:underline">
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
}
