import { useState } from 'react'
import { Key, Plus, X, Copy, Check, Trash2, Shield, Loader2 } from 'lucide-react'
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '../../hooks/useApiKeys'
import { useAllPermissions } from '../../hooks/useAdmin'
import LoadingSpinner from '../../components/LoadingSpinner'

function CreateKeyModal({ onClose }: { onClose: () => void }) {
  const create = useCreateApiKey()
  const { data: allPerms } = useAllPermissions()
  const [name, setName] = useState('')
  const [selectedScopes, setSelectedScopes] = useState<Set<string>>(new Set())
  const [expiresInDays, setExpiresInDays] = useState('')
  const [createdKey, setCreatedKey] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const toggleScope = (scope: string) => {
    const next = new Set(selectedScopes)
    if (next.has(scope)) next.delete(scope)
    else next.add(scope)
    setSelectedScopes(next)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const res = await create.mutateAsync({
        name,
        scopes: Array.from(selectedScopes),
        expires_in_days: expiresInDays ? parseInt(expiresInDays, 10) : null,
      })
      setCreatedKey(res.key)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create API key')
    }
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(createdKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (createdKey) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
        <div className="w-full max-w-md rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">API Key Created</h3>
            <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800">
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mb-3">
            Copy this key now — it will never be shown again.
          </p>
          <div className="flex items-center gap-2 rounded-lg bg-surface-100 dark:bg-surface-800 p-3 mb-4">
            <code className="flex-1 text-xs font-mono text-surface-700 dark:text-surface-300 break-all">
              {createdKey}
            </code>
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-md text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-950/20"
              aria-label="Copy"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <button onClick={onClose} className="btn-primary w-full">Done</button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Create API Key</h3>
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
            <input className="input-modern" value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Integration Server" />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Expires in (days, optional)</label>
            <input type="number" min={1} max={365} className="input-modern" value={expiresInDays} onChange={(e) => setExpiresInDays(e.target.value)} placeholder="Never" />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Scopes</label>
            {allPerms && allPerms.length > 0 ? (
              <div className="space-y-1 max-h-60 overflow-y-auto pr-1 border border-surface-200 dark:border-surface-700 rounded-xl p-2">
                {allPerms.map((perm) => (
                  <label key={perm} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-50 dark:hover:bg-surface-800/40 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedScopes.has(perm)}
                      onChange={() => toggleScope(perm)}
                      className="rounded border-surface-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-xs font-mono text-surface-700 dark:text-surface-300">{perm}</span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="text-xs text-surface-400 dark:text-surface-500">No permissions available.</p>
            )}
          </div>
          <button type="submit" disabled={create.isPending} className="btn-primary w-full">
            {create.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Key'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function ApiKeysPage() {
  const { data: keys, isLoading, isError } = useApiKeys()
  const revoke = useRevokeApiKey()
  const [showCreate, setShowCreate] = useState(false)

  if (isLoading) return <LoadingSpinner />
  if (isError) return <div className="p-6 text-red-600 dark:text-red-400">Failed to load API keys.</div>

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-surface-100">API Keys</h1>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-0.5">Manage machine-to-machine access keys.</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Create Key
        </button>
      </div>

      {keys && keys.length > 0 ? (
        <div className="card-modern overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-50 dark:bg-surface-800/50 text-xs uppercase tracking-wider text-surface-500 dark:text-surface-400">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Prefix</th>
                <th className="px-4 py-3 text-left font-medium">Scopes</th>
                <th className="px-4 py-3 text-left font-medium">Expires</th>
                <th className="px-4 py-3 text-left font-medium">Last Used</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
              {keys.map((key) => (
                <tr key={key.id} className="hover:bg-surface-50 dark:hover:bg-surface-800/30 transition-colors">
                  <td className="px-4 py-3 font-medium text-surface-900 dark:text-surface-100">{key.name}</td>
                  <td className="px-4 py-3">
                    <code className="text-xs font-mono bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 rounded text-surface-600 dark:text-surface-300">{key.key_prefix}...</code>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <Shield className="w-3 h-3 text-surface-400" />
                      <span className="text-xs text-surface-500 dark:text-surface-400">{key.scopes.length}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-surface-500 dark:text-surface-400">
                    {key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-surface-500 dark:text-surface-400">
                    {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => revoke.mutate(key.id)}
                      disabled={revoke.isPending}
                      className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-40"
                      aria-label="Revoke"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card-modern p-8 text-center">
          <Key className="w-10 h-10 text-surface-300 dark:text-surface-600 mx-auto mb-3" />
          <p className="text-sm text-surface-500 dark:text-surface-400">No API keys yet.</p>
          <button onClick={() => setShowCreate(true)} className="text-sm text-primary-600 dark:text-primary-400 hover:underline mt-2">
            Create your first key
          </button>
        </div>
      )}

      {showCreate && <CreateKeyModal onClose={() => setShowCreate(false)} />}
    </div>
  )
}
