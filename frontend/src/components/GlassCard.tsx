import { ReactNode } from 'react'

interface GlassCardProps {
  children: ReactNode
  className?: string
  hover?: boolean
  depth?: 1 | 2 | 3
}

export function GlassCard({ children, className = '', hover = false, depth = 2 }: GlassCardProps) {
  const depthClass = depth === 1 ? 'depth-1' : depth === 2 ? 'depth-2' : 'depth-3'
  const hoverClass = hover ? 'hover:-translate-y-0.5 transition-transform duration-300' : ''

  return (
    <div
      className={`rounded-2xl border border-white/30 dark:border-white/10 ${depthClass} ${hoverClass} ${className}`}
      style={{
        background: 'rgba(255, 255, 255, 0.55)',
        backdropFilter: 'blur(16px) saturate(180%)',
        WebkitBackdropFilter: 'blur(16px) saturate(180%)',
      }}
    >
      {children}
    </div>
  )
}
