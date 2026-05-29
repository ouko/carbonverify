import { useState } from 'react'
import { Users, Search, Plus, UserCheck, UserX, Shield, Lock, ChevronRight, X, Loader2, Link2, Copy, Check } from 'lucide-react'
import { useUsers, useCreateUser, useUpdateUser, useDeactivateUser, useReactivateUser, useCreateInvite } from '../../hooks/useAdmin'
import LoadingSpinner from '../../components/LoadingSpinner'
import type { User } from '../../types'

const roleBadge: Record<string, string> = {
  admin: 'badge-red',
  operator: 'badge-amber',
  developer: 'badge-blue',
  viewer: 'badge-slate',
}

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const create = useCreateUser()
  const [form, setForm] = useState({ name: '', email: '', role: 'viewer', password: '' })
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await create.mutateAsync(form)
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create user')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Create User</h3>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800">
            <X className="h-4 w-4" />
          </button>
        </div>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-600 dark:text-red-400">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Name</label>
            <input className="input-modern" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Email</label>
            <input type="email" className="input-modern" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Role</label>
            <select className="input-modern" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as User['role'] })}>
              <option value="viewer">Viewer</option>
              <option value="developer">Developer</option>
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Password</label>
            <input type="password" className="input-modern" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} />
          </div>
          <button type="submit" disabled={create.isPending} className="btn-primary w-full disabled:opacity-50">
            {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {create.isPending ? ' Creating…' : ' Create User'}
          </button>
        </form>
      </div>
    </div>
  )
}

function EditUserDrawer({ user, onClose }: { user: User; onClose: () => void }) {
  const update = useUpdateUser()
  const [form, setForm] = useState({ name: user.name, email: user.email, role: user.role, is_active: user.is_active })
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await update.mutateAsync({ id: user.id, updates: form })
      onClose()
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to update user')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-surface-950/40 backdrop-blur-sm">
      <div className="w-full max-w-md h-full bg-white dark:bg-surface-900 border-l border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Edit User</h3>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800">
            <X className="h-4 w-4" />
          </button>
        </div>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-600 dark:text-red-400">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Name</label>
            <input className="input-modern" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Email</label>
            <input type="email" className="input-modern" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Role</label>
            <select className="input-modern" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as User['role'] })}>
              <option value="viewer">Viewer</option>
              <option value="developer">Developer</option>
              <option value="operator">Operator</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex items-center gap-2 py-2">
            <input
              type="checkbox"
              id="is_active"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              className="w-4 h-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
            />
            <label htmlFor="is_active" className="text-sm text-surface-700 dark:text-surface-300">Account Active</label>
          </div>
          <button type="submit" disabled={update.isPending} className="btn-primary w-full disabled:opacity-50">
            {update.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Changes'}
          </button>
        </form>
      </div>
    </div>
  )
}

function GenerateInviteModal({ onClose }: { onClose: () => void }) {
  const createInvite = useCreateInvite()
  const [form, setForm] = useState({ name: '', email: '', role: 'viewer' })
  const [error, setError] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [copied, setCopied] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const data = await createInvite.mutateAsync(form)
      const url = `${window.location.origin}/register?invite=${data.token}`
      setInviteUrl(url)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create invite')
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Generate Invite</h3>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800">
            <X className="h-4 w-4" />
          </button>
        </div>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-600 dark:text-red-400">{error}</div>
        )}
        {inviteUrl ? (
          <div className="space-y-4">
            <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/20 p-4 text-center">
              <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">Invite Generated</p>
              <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-1">Share this link with the user</p>
            </div>
            <div className="flex items-center gap-2">
              <input readOnly value={inviteUrl} className="input-modern flex-1 text-xs" />
              <button onClick={handleCopy} className="btn-secondary p-2.5" title="Copy invite link">
                {copied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <button onClick={onClose} className="btn-primary w-full">Done</button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Name</label>
              <input className="input-modern" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Email</label>
              <input type="email" className="input-modern" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Role</label>
              <select className="input-modern" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="viewer">Viewer</option>
                <option value="developer">Developer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <button type="submit" disabled={createInvite.isPending} className="btn-primary w-full disabled:opacity-50">
              {createInvite.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
              {createInvite.isPending ? ' Generating…' : ' Generate Invite Link'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

export default function UserManagementPage() {
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [showInvite, setShowInvite] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)

  const filters = {
    search: search || undefined,
    role: roleFilter !== 'all' ? roleFilter : undefined,
    is_active: statusFilter !== 'all' ? (statusFilter === 'active') : undefined,
  }

  const { data: users, isLoading, isError } = useUsers(filters)
  const deactivate = useDeactivateUser()
  const reactivate = useReactivateUser()

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="page-title">User Management</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500 mt-1">
            Create, manage, and provision user accounts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowInvite(true)} className="btn-secondary text-sm">
            <Link2 className="w-4 h-4" /> Invite
          </button>
          <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
            <Plus className="w-4 h-4" /> Create User
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-modern pl-10"
          />
        </div>
        <div className="flex gap-2">
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="input-modern py-2 px-3 text-xs appearance-none cursor-pointer">
            <option value="all">All Roles</option>
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="developer">Developer</option>
            <option value="viewer">Viewer</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)} className="input-modern py-2 px-3 text-xs appearance-none cursor-pointer">
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {isError ? (
        <div className="card p-8 text-center">
          <p className="text-red-600 dark:text-red-400 font-medium">Failed to load users</p>
        </div>
      ) : isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-200/60 dark:border-surface-800/40">
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">User</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Role</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider">MFA</th>
                  <th className="px-6 py-3.5 font-semibold text-surface-500 dark:text-surface-400 text-xs uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {users?.map((user) => (
                  <tr key={user.id} className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-semibold text-surface-900 dark:text-surface-100">{user.name}</p>
                        <p className="text-xs text-surface-400 dark:text-surface-500">{user.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${roleBadge[user.role]} text-[10px] capitalize`}>{user.role}</span>
                    </td>
                    <td className="px-6 py-4">
                      {user.is_active ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                          <UserCheck className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                          <UserX className="w-3 h-3" /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {user.mfa_enabled ? (
                        <span className="inline-flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400">
                          <Shield className="w-3 h-3" /> On
                        </span>
                      ) : (
                        <span className="text-xs text-surface-400 dark:text-surface-500">Off</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditingUser(user)}
                          className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
                          aria-label="Edit user"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                        {user.is_active ? (
                          <button
                            onClick={() => deactivate.mutate(user.id)}
                            disabled={deactivate.isPending}
                            className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
                            aria-label="Deactivate user"
                            title="Deactivate"
                          >
                            <Lock className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => reactivate.mutate(user.id)}
                            disabled={reactivate.isPending}
                            className="p-1.5 rounded-lg text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/20 transition-colors disabled:opacity-40"
                            aria-label="Reactivate user"
                            title="Reactivate"
                          >
                            <UserCheck className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {users?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-surface-400 dark:text-surface-500">
                      <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} />}
      {showInvite && <GenerateInviteModal onClose={() => setShowInvite(false)} />}
      {editingUser && <EditUserDrawer user={editingUser} onClose={() => setEditingUser(null)} />}
    </div>
  )
}
