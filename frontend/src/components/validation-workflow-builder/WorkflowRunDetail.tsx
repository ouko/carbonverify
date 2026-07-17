import { useState } from 'react'
import { useValidationRun, useStepExecutions, useProofs, useTransitions } from '../../hooks/useValidationWorkflows'
import LoadingSpinner from '../LoadingSpinner'

interface WorkflowRunDetailProps {
  runId: string
}

export function WorkflowRunDetail({ runId }: WorkflowRunDetailProps) {
  const { data: run } = useValidationRun(runId)
  const { data: steps } = useStepExecutions(runId)
  const { data: proofs } = useProofs(runId)
  const { data: transitions } = useTransitions(runId)
  const [tab, setTab] = useState<'overview' | 'steps' | 'proofs' | 'transitions'>('overview')

  if (!run) return <LoadingSpinner />

  return (
    <div className="space-y-4">
      <div className="flex gap-2 border-b border-surface-200 dark:border-surface-700">
        {(['overview', 'steps', 'proofs', 'transitions'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm capitalize ${tab === t ? 'text-primary-600 border-b-2 border-primary-600' : 'text-surface-500'}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="card p-4 space-y-2 text-sm">
          <p><span className="text-surface-500">Status:</span> {run.status}</p>
          <p><span className="text-surface-500">Trigger:</span> {run.trigger_event}</p>
          {run.confidence_score !== undefined && <p><span className="text-surface-500">Confidence:</span> {run.confidence_score}</p>}
          {run.error_message && <p className="text-red-600 dark:text-red-400">Error: {run.error_message}</p>}
          {run.merkle_root && <p className="font-mono text-xs break-all">Merkle: {run.merkle_root}</p>}
        </div>
      )}

      {tab === 'steps' && (
        <ul className="space-y-2">
          {steps?.map((step) => (
            <li key={step.id} className="card p-3 text-sm">
              <p className="font-medium">{step.step_name} <span className="text-surface-500">({step.step_id})</span></p>
              <p className="text-xs text-surface-500">{step.status} {step.duration_ms ? `• ${step.duration_ms}ms` : ''}</p>
              {step.error_message && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{step.error_message}</p>}
            </li>
          ))}
        </ul>
      )}

      {tab === 'proofs' && (
        <ul className="space-y-2">
          {proofs?.map((proof) => (
            <li key={proof.id} className="card p-3 text-sm">
              <p className="font-medium">{proof.proof_type}</p>
              <p className="text-xs text-surface-500 font-mono break-all">{proof.proof_hash}</p>
              <p className="text-xs text-surface-400">{proof.captured_at}</p>
            </li>
          ))}
        </ul>
      )}

      {tab === 'transitions' && (
        <ul className="space-y-2">
          {transitions?.map((t) => (
            <li key={t.id} className="card p-3 text-sm">
              <p>{t.from_state} → {t.to_state}</p>
              <p className="text-xs text-surface-500 font-mono break-all">{t.transition_hash}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
