import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import LoadingSpinner from './LoadingSpinner'

interface ProtectedRouteProps {
  requiredRole?: 'admin' | 'operator' | 'developer' | 'viewer'
}

export default function ProtectedRoute({ requiredRole }: ProtectedRouteProps = {}) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)
  const user = useAuthStore((s) => s.user)

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

  if (requiredRole && user) {
    const roleHierarchy = ['viewer', 'developer', 'operator', 'admin']
    const userLevel = roleHierarchy.indexOf(user.role)
    const requiredLevel = roleHierarchy.indexOf(requiredRole)
    if (userLevel < requiredLevel) {
      return <Navigate to="/" replace />
    }
  }

  return <Outlet />
}
