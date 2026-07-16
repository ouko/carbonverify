interface SimpleModeToggleProps {
  showAdvanced: boolean
  onChange: (showAdvanced: boolean) => void
}

export function SimpleModeToggle({ showAdvanced, onChange }: SimpleModeToggleProps) {
  return (
    <button
      type="button"
      onClick={() => onChange(!showAdvanced)}
      className="inline-flex items-center gap-2 text-sm text-surface-600 dark:text-surface-400 hover:text-surface-900 dark:hover:text-surface-200"
      aria-pressed={showAdvanced}
    >
      <span
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
          showAdvanced ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
            showAdvanced ? 'translate-x-5' : 'translate-x-1'
          }`}
        />
      </span>
      <span>Show advanced fields</span>
    </button>
  )
}
