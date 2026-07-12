export function WizardStepper({ current, steps }: { current: number; steps: string[] }) {
  return (
    <div className="flex items-center space-x-2 mb-6">
      {steps.map((label, idx) => (
        <div key={label} className={`flex items-center ${idx > 0 ? 'ml-2' : ''}`}>
          {idx > 0 && <span className="mx-2 text-gray-500">&gt;</span>}
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              idx === current
                ? 'bg-emerald-600 text-white'
                : idx < current
                ? 'bg-emerald-100 text-emerald-800'
                : 'bg-gray-100 text-gray-600'
            }`}
          >
            {idx + 1}. {label}
          </span>
        </div>
      ))}
    </div>
  )
}
