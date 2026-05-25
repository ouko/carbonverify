import type { ReactNode } from 'react'

interface StatCardProps {
  title: string
  value: string | number
  icon: ReactNode
  subtitle?: string
  trend?: { value: number; positive: boolean }
  color?: 'emerald' | 'blue' | 'amber' | 'rose' | 'violet'
  delay?: number
}

const colorMap = {
  emerald: 'from-primary-500/10 to-primary-600/5 text-primary-600 dark:text-primary-400',
  blue: 'from-blue-500/10 to-blue-600/5 text-blue-600 dark:text-blue-400',
  amber: 'from-amber-500/10 to-amber-600/5 text-amber-600 dark:text-amber-400',
  rose: 'from-rose-500/10 to-rose-600/5 text-rose-600 dark:text-rose-400',
  violet: 'from-violet-500/10 to-violet-600/5 text-violet-600 dark:text-violet-400',
}

const iconBgMap = {
  emerald: 'bg-primary-500/10 text-primary-600 dark:text-primary-400',
  blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  violet: 'bg-violet-500/10 text-violet-600 dark:text-violet-400',
}

export default function StatCard({ title, value, icon, subtitle, trend, color = 'emerald', delay = 0 }: StatCardProps) {
  return (
    <div
      className="stat-card relative overflow-hidden"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Background gradient */}
      <div className={`absolute inset-0 bg-gradient-to-br ${colorMap[color]} opacity-50`} />
      
      <div className="relative">
        <div className="flex items-start justify-between mb-4">
          <div className={`p-2.5 rounded-xl ${iconBgMap[color]}`}>
            {icon}
          </div>
          {trend && (
            <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full ${
              trend.positive
                ? 'bg-primary-50 text-primary-700 dark:bg-primary-950/40 dark:text-primary-300'
                : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
            }`}>
              {trend.positive ? '+' : ''}{trend.value}%
            </div>
          )}
        </div>
        
        <div className="text-3xl font-bold tracking-tight text-surface-900 dark:text-surface-100 mb-1">
          {value}
        </div>
        <div className="text-sm font-medium text-surface-500 dark:text-surface-400">
          {title}
        </div>
        {subtitle && (
          <div className="text-xs text-surface-400 dark:text-surface-500 mt-1">
            {subtitle}
          </div>
        )}
      </div>
    </div>
  )
}
