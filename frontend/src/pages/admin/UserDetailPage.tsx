import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Shield, ShieldCheck, ShieldX, UserCheck, UserX, Lock, Monitor, Loader2, X, LogOut } from 'lucide-react'
import { useUser, useUpdateUser, useUserPermissions, useGrantPermission, useRevokePermission, useUserSessions, useRevokeSession, useForceLogoutUser, useAllPermissions } from '../../hooks/useAdmin'
import LoadingSpinner from '../../components/LoadingSpinner'
import type { UserDetail } from '../../types'

function PermissionsEditor({ user }: { user: UserDetail }) {
  const { data: allPerms } = useAllPermissions()
  const { data: effectivePerms } = useUserPermissions(user.id)
  const grant = useGrantPermission()
  const revoke = useRevokePermission()

  const grantedSet = new Set(effectivePerms || [])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <Shield className="w-4 h-4 text-primary-500" />
        <h4 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Effective Permissions</h4>
        <span className="text-xs text-surface-400 dark:text-surface-500">({grantedSet.size})</span>
      </div>
      {allPerms && allPerms.length > 0 && (
        <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
          {allPerms.map((perm) => {
            const has = grantedSet.has(perm)
            return (
              <div key={perm} className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-surface-50 dark:hover:bg-surface-800/40">
                <div className="flex items-center gap-2">
                  {has ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <ShieldX className="w-3.5 h-3.5 text-surface-300 dark:text-surface-600" />
                  )}
                  <span className="text-xs font-medium text-surface-700 dark:text-surface-300 font-mono">{perm}</span>
                </div>
                <button
                  onClick={() => has ? revoke.mutate({ userId: user.id, permission: perm }) : grant.mutate({ userId: user.id, permission: perm })}
                  disabled={grant.isPending || revoke.isPending}
                  className={`text-[10px] px-2.5 py-1 rounded-md font-semibold transition-colors disabled:opacity-40 ${
                    has
                      ? 'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-950/30'
                      : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-950/30'
                  }`}
                >
                  {has ? 'Revoke' : 'Grant'}
                </button>
              </div>
            )
          })}
        </div>
      )}
      {(!allPerms || allPerms.length === 0) && (
        <p className="text-xs text-surface-400 dark:text-surface-500">No permissions available.</p>
      )}
    </div>
  )
}

function UserSessions({ userId }: { userId: string }) {
  const { data: sessions, isLoading } = useUserSessions(userId)
  const revoke = useRevokeSession()

  if (isLoading) return <LoadingSpinner />

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <Monitor className="w-4 h-4 text-blue-500" />
        <h4 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Active Sessions</h4>
        <span className="text-xs text-surface-400 dark:text-surface-500">({sessions?.length ?? 0})</span>
      </div>
      {sessions?.map((session) => (
        <div key={session.id} className="flex items-center justify-between rounded-xl bg-surface-50 dark:bg-surface-800/40 px-4 py-3">
          <div>
            <p className="text-xs font-semibold text-surface-900 dark:text-surface-100">{session.device || 'Unknown device'}</p>
            <p className="text-[10px] text-surface-400 dark:text-surface-500">{session.ip} &middot; {session.last_active ? new Date(session.last_active).toLocaleString() : 'N/A'}</p>
          </div>
          <div className="flex items-center gap-2">
            {session.current && (
              <span className="text-[10px] font-semibold text-primary-600 dark:text-primary-400 bg-primary-50 dark:bg-primary-950/20 px-2 py-0.5 rounded-full">Current</span>
            )}
            <button
              onClick={() => revoke.mutate({ userId, sessionId: session.id })}
              disabled={revoke.isPending}
              className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
              aria-label="Revoke session"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ))}
      {(!sessions || sessions.length === 0) && (
        <p className="text-xs text-surface-400 dark:text-surface-500">No active sessions.</p>
      )}
    </div>
  )
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: user, isLoading, isError } = useUser(id!)
  const update = useUpdateUser()
  const forceLogout = useForceLogoutUser()
  const [error, setError] = useState('')

  const handleToggleActive = async () => {
    setError('')
    try {
      await update.mutateAsync({ id: id!, updates: { is_active: !user?.is_active } })
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to update user')
    }
  }

  const handleForceLogout = async () => {
    if (!window.confirm(`Force logout ${user?.name}? This will revoke all active sessions.`)) return
    setError('')
    try {
      await forceLogout.mutateAsync(id!)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to force logout')
    }
  }

  if (isLoading) return <LoadingSpinner />
  if (isError || !user) {
    return (
      <div className="card p-8 text-center">
        <p className="text-red-600 dark:text-red-400 font-medium">User not found</p>
        <button onClick={() => navigate('/admin/users')} className="btn-secondary text-sm mt-4">
          <ArrowLeft className="w-4 h-4" /> Back to Users
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/admin/users')} className="p-2 rounded-xl hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-400 transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div>
          <h2 className="page-title">{user.name}</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500">{user.email}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={handleToggleActive}
            disabled={update.isPending}
            className={`btn-secondary text-xs ${user.is_active ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}
          >
            {update.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : user.is_active ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
            {user.is_active ? ' Deactivate' : ' Reactivate'}
          </button>
          <button onClick={handleForceLogout} disabled={forceLogout.isPending} className="btn-secondary text-xs text-red-600 dark:text-red-400">
            {forceLogout.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
            Force Logout
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-600 dark:text-red-400">{error}</div>
      )}

      {/* Profile info */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Profile</h3>
          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Role</p>
              <span className={`badge ${
                user.role === 'admin' ? 'badge-red' : user.role === 'operator' ? 'badge-amber' : user.role === 'developer' ? 'badge-blue' : 'badge-slate'
              } text-[10px] capitalize mt-1 inline-block`}>{user.role}</span>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Status</p>
              <p className="text-sm text-surface-700 dark:text-surface-300 mt-0.5 flex items-center gap-1">
                {user.is_active ? <UserCheck className="w-3.5 h-3.5 text-emerald-500" /> : <UserX className="w-3.5 h-3.5 text-red-500" />}
                {user.is_active ? 'Active' : 'Inactive'}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">MFA</p>
              <p className="text-sm text-surface-700 dark:text-surface-300 mt-0.5 flex items-center gap-1">
                {user.mfa_enabled ? <ShieldCheck className="w-3.5 h-3.5 text-violet-500" /> : <ShieldX className="w-3.5 h-3.5 text-surface-400" />}
                {user.mfa_enabled ? 'Enabled' : 'Disabled'}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Created</p>
              <p className="text-sm text-surface-700 dark:text-surface-300 mt-0.5">{new Date(user.created_at).toLocaleString()}</p>
            </div>
            {user.last_login_at && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Last Login</p>
                <p className="text-sm text-surface-700 dark:text-surface-300 mt-0.5">{new Date(user.last_login_at).toLocaleString()}</p>
              </div>
            )}
            {user.locked_until && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Locked Until</p>
                <p className="text-sm text-red-600 dark:text-red-400 mt-0.5 flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5" /> {new Date(user.locked_until).toLocaleString()}
                </p>
              </div>
            )}
            {user.failed_login_count > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-surface-400 dark:text-surface-500">Failed Logins</p>
                <p className="text-sm text-red-600 dark:text-red-400 mt-0.5">{user.failed_login_count}</p>
              </div>
            )}
          </div>
        </div>

        <div className="card p-5 lg:col-span-2">
          <PermissionsEditor user={user} />
        </div>
      </div>

      {/* Sessions */}
      <div className="card p-5">
        <UserSessions userId={user.id} />
      </div>
    </div>
  )
}
