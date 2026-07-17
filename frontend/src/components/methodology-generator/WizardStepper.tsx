export function WizardStepper({ current, steps }: { current: number; steps: string[] }) {
  return (
    <div className="flex items-center space-x-2 mb-6">
      {steps.map((label, idx) => (
        <div key={label} className={`flex items-center ${idx > 0 ? 'ml-2' : ''}`}>
          {idx > 0 && <span className="mx-2 text-surface-400 dark:text-surface-500">&gt;</span>}
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              idx === current
                ? 'bg-emerald-600 text-white'
                : idx < current
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                : 'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400'
            }`}
          >
            {idx + 1}. {label}
          </span>
        </div>
      ))}
    </div>
  )
}
