interface MultiSelectChipsProps {
  label?: string
  options: string[]
  selected: string[]
  onChange: (selected: string[]) => void
  allowCustom?: boolean
}

export function MultiSelectChips({ label, options, selected, onChange, allowCustom = false }: MultiSelectChipsProps) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value))
    } else {
      onChange([...selected, value])
    }
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          {label}
        </label>
      )}
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
              selected.includes(opt)
                ? 'bg-primary-100 border-primary-400 text-primary-800 dark:bg-primary-950 dark:border-primary-600 dark:text-primary-200'
                : 'bg-white border-surface-200 text-surface-600 hover:border-primary-300 dark:bg-surface-900 dark:border-surface-700 dark:text-surface-400'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
      {allowCustom && (
        <input
          type="text"
          placeholder="Add custom and press Enter"
          className="input-modern mt-2 text-xs"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              const value = e.currentTarget.value.trim()
              if (value && !selected.includes(value)) {
                onChange([...selected, value])
                e.currentTarget.value = ''
              }
            }
          }}
        />
      )}
    </div>
  )
}
