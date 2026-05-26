import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

interface BreadcrumbItem {
  label: string
  to?: string
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[]
}

export default function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400 mb-4">
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-2">
          {index > 0 && <ChevronRight className="h-4 w-4" />}
          {item.to ? (
            <Link to={item.to} className="hover:text-primary-600 dark:hover:text-primary-400 transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-surface-900 dark:text-surface-100 font-medium">{item.label}</span>
          )}
        </div>
      ))}
    </nav>
  )
}
