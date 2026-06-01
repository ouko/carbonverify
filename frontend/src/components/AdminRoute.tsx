import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import LoadingSpinner from './LoadingSpinner'
import type { User } from '../types'

const ADMIN_PERMISSIONS = [
  'users:read',
  'users:create',
  'users:update',
  'users:delete',
  'users:manage_permissions',
  'users:manage_roles',
  'users:manage_sessions',
  'system:configure',
  'audit:read',
  'audit:export',
  'audit:anchor',
  'compliance:admin',
  'tokenization:admin',
]

function hasAdminAccess(user: User | null): boolean {
  if (!user) return false
  if (user.role === 'admin') return true
  const granted = user.permissions?.granted || []
  return ADMIN_PERMISSIONS.some((p) => granted.includes(p))
}

export default function AdminRoute() {
  const user = useAuthStore((s) => s.user)
  const isLoading = useAuthStore((s) => s.isLoading)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-50 dark:bg-surface-950">
        <LoadingSpinner />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!hasAdminAccess(user)) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
