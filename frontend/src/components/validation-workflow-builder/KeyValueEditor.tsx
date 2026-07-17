import { useState, useEffect } from 'react'

interface KeyValueEditorProps {
  value: Record<string, string>
  onChange: (value: Record<string, string>) => void
  label?: string
}

export function KeyValueEditor({ value, onChange, label }: KeyValueEditorProps) {
  const [pairs, setPairs] = useState<{ key: string; value: string }[]>(
    Object.entries(value).map(([k, v]) => ({ key: k, value: v }))
  )

  useEffect(() => {
    setPairs(Object.entries(value).map(([k, v]) => ({ key: k, value: v })))
  }, [value])

  const emit = (next: { key: string; value: string }[]) => {
    const record: Record<string, string> = {}
    next.forEach((p) => {
      if (p.key) record[p.key] = p.value
    })
    onChange(record)
  }

  const update = (index: number, field: 'key' | 'value', val: string) => {
    const next = pairs.map((p, i) => (i === index ? { ...p, [field]: val } : p))
    setPairs(next)
    emit(next)
  }

  const addPair = () => setPairs([...pairs, { key: '', value: '' }])

  const removePair = (index: number) => {
    const next = pairs.filter((_, i) => i !== index)
    setPairs(next)
    emit(next)
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1">
          {label}
        </label>
      )}
      <div className="space-y-2">
        {pairs.map((p, i) => (
          <div key={i} className="flex gap-2">
            <input
              value={p.key}
              onChange={(e) => update(i, 'key', e.target.value)}
              placeholder="Key"
              className="input-modern flex-1"
            />
            <input
              value={p.value}
              onChange={(e) => update(i, 'value', e.target.value)}
              placeholder="Value"
              className="input-modern flex-1"
            />
            <button type="button" onClick={() => removePair(i)} className="btn-ghost text-red-500">
              Remove
            </button>
          </div>
        ))}
      </div>
      <button type="button" onClick={addPair} className="btn-secondary mt-2 text-xs">
        + Add
      </button>
    </div>
  )
}
