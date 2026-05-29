import { useAuthStore } from '../stores/authStore'

export function RequirePermission({
  permission,
  children,
  fallback = null,
}: {
  permission: string
  children: React.ReactNode
  fallback?: React.ReactNode
}) {
  const user = useAuthStore((s) => s.user)
  const hasPerm =
    user?.role === 'admin' ||
    (user?.permissions?.granted || []).includes(permission)
  return hasPerm ? <>{children}</> : <>{fallback}</>
}
