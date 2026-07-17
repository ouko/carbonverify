import { useState, useEffect } from 'react'

interface JsonEditorProps {
  label?: string
  value: unknown
  onChange: (value: unknown) => void
  error?: string
  rows?: number
}

export function JsonEditor({ label, value, onChange, error, rows = 6 }: JsonEditorProps) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2))
  const [parseError, setParseError] = useState<string | null>(null)

  useEffect(() => {
    setText(JSON.stringify(value, null, 2))
  }, [value])

  const handleBlur = () => {
    try {
      const parsed = JSON.parse(text)
      setParseError(null)
      onChange(parsed)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          {label}
        </label>
      )}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        rows={rows}
        className="input-modern font-mono text-xs"
        spellCheck={false}
      />
      {(parseError || error) && (
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">{parseError || error}</p>
      )}
    </div>
  )
}
