import { JsonEditor } from './JsonEditor'
import { KeyValueEditor } from './KeyValueEditor'
import { MultiSelectChips } from './MultiSelectChips'
import type { WorkflowGraph, WorkflowStep, WorkflowStepType } from '../../types'

interface StepConfigPanelProps {
  step: WorkflowStep | null
  graph: WorkflowGraph
  onChangeStep: (step: WorkflowStep) => void
  onRemoveStep: (id: string) => void
}

const STEP_TYPE_LABELS: Record<WorkflowStepType, string> = {
  http_request: 'HTTP Request',
  database_query: 'Database Query',
  service_call: 'Service Call',
  external_api: 'External API',
  notification: 'Notification',
  dom_capture: 'DOM Capture',
  decision_gate: 'Decision Gate',
  ai_evaluation: 'AI Evaluation',
  wait: 'Wait',
  parallel: 'Parallel',
  subflow: 'Subflow',
}

export function StepConfigPanel({ step, graph, onChangeStep, onRemoveStep }: StepConfigPanelProps) {
  if (!step) {
    return (
      <div className="p-8 text-center text-surface-500 dark:text-surface-400 text-sm">
        Select a step to configure it.
      </div>
    )
  }

  const patch = (partial: Partial<WorkflowStep>) => onChangeStep({ ...step, ...partial })
  const patchConfig = (partial: Record<string, unknown>) =>
    patch({ config: { ...step.config, ...partial } })

  const stepOptions = ['end', 'fail', ...graph.steps.filter((s) => s.id !== step.id).map((s) => s.id)]

  return (
    <div className="p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">
          {STEP_TYPE_LABELS[step.type]} Configuration
        </h3>
        <button type="button" onClick={() => onRemoveStep(step.id)} className="btn-red text-xs">
          Delete
        </button>
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Step ID</label>
        <input value={step.id} onChange={(e) => patch({ id: e.target.value })} className="input-modern font-mono" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Name</label>
        <input value={step.name} onChange={(e) => patch({ name: e.target.value })} className="input-modern" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Description</label>
        <textarea
          value={step.description || ''}
          onChange={(e) => patch({ description: e.target.value })}
          rows={2}
          className="input-modern"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Timeout (ms)</label>
          <input
            type="number"
            value={step.timeout_ms}
            onChange={(e) => patch({ timeout_ms: Number(e.target.value) })}
            className="input-modern"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
          <input type="checkbox" checked={step.enabled} onChange={(e) => patch({ enabled: e.target.checked })} />
          Enabled
        </label>
        <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
          <input type="checkbox" checked={step.capture_proof} onChange={(e) => patch({ capture_proof: e.target.checked })} />
          Capture proof
        </label>
        <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
          <input type="checkbox" checked={step.checkpoint} onChange={(e) => patch({ checkpoint: e.target.checked })} />
          Checkpoint
        </label>
        <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
          <input type="checkbox" checked={step.skippable} onChange={(e) => patch({ skippable: e.target.checked })} />
          Skippable
        </label>
      </div>

      <MultiSelectChips
        label="Next on success"
        options={stepOptions}
        selected={step.next_on_success}
        onChange={(next) => patch({ next_on_success: next })}
      />

      <MultiSelectChips
        label="Next on failure"
        options={stepOptions}
        selected={step.next_on_failure}
        onChange={(next) => patch({ next_on_failure: next })}
      />

      <div className="border-t border-surface-200 dark:border-surface-700 pt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
          Type-specific config
        </h4>
        <StepTypeConfig step={step} onPatchConfig={patchConfig} />
      </div>
    </div>
  )
}

function StepTypeConfig({
  step,
  onPatchConfig,
}: {
  step: WorkflowStep
  onPatchConfig: (partial: Record<string, unknown>) => void
}) {
  const cfg = step.config

  switch (step.type) {
    case 'ai_evaluation':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Prompt</label>
            <textarea
              value={(cfg.prompt as string) || ''}
              onChange={(e) => onPatchConfig({ prompt: e.target.value })}
              rows={5}
              className="input-modern"
            />
          </div>
          <JsonEditor
            label="Input data"
            value={(cfg.input_data as Record<string, unknown>) || {}}
            onChange={(v) => onPatchConfig({ input_data: v })}
          />
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Pass threshold: {((cfg.pass_threshold as number) ?? 0.7).toFixed(2)}
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={(cfg.pass_threshold as number) ?? 0.7}
              onChange={(e) => onPatchConfig({ pass_threshold: Number(e.target.value) })}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Temperature</label>
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={(cfg.temperature as number) ?? 0.2}
              onChange={(e) => onPatchConfig({ temperature: Number(e.target.value) })}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Max tokens</label>
            <input
              type="number"
              min={100}
              max={8192}
              value={(cfg.max_tokens as number) ?? 1536}
              onChange={(e) => onPatchConfig({ max_tokens: Number(e.target.value) })}
              className="input-modern"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
            <input
              type="checkbox"
              checked={(cfg.fail_on_error as boolean) ?? true}
              onChange={(e) => onPatchConfig({ fail_on_error: e.target.checked })}
            />
            Fail on error
          </label>
        </div>
      )

    case 'http_request':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Method</label>
            <select
              value={(cfg.method as string) || 'GET'}
              onChange={(e) => onPatchConfig({ method: e.target.value })}
              className="input-modern w-full"
            >
              {['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">URL</label>
            <input
              value={(cfg.url as string) || ''}
              onChange={(e) => onPatchConfig({ url: e.target.value })}
              className="input-modern"
            />
          </div>
          <KeyValueEditor
            label="Headers"
            value={(cfg.headers as Record<string, string>) || {}}
            onChange={(v) => onPatchConfig({ headers: v })}
          />
          <JsonEditor label="Body" value={(cfg.body as Record<string, unknown>) || null} onChange={(v) => onPatchConfig({ body: v })} />
          <MultiSelectChips
            label="Expected status codes"
            options={['200', '201', '204', '400', '401', '403', '404', '500']}
            selected={((cfg.expected_status_codes as number[]) || []).map(String)}
            onChange={(v) => onPatchConfig({ expected_status_codes: v.map(Number) })}
            allowCustom
          />
        </div>
      )

    case 'database_query':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Query</label>
            <textarea
              value={(cfg.query as string) || ''}
              onChange={(e) => onPatchConfig({ query: e.target.value })}
              rows={4}
              className="input-modern font-mono text-xs"
            />
          </div>
          <JsonEditor label="Params" value={(cfg.params as Record<string, unknown>) || {}} onChange={(v) => onPatchConfig({ params: v })} />
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Expected row count (optional)
            </label>
            <input
              type="number"
              value={(cfg.expected_row_count as number) ?? ''}
              onChange={(e) =>
                onPatchConfig({ expected_row_count: e.target.value ? Number(e.target.value) : null })
              }
              className="input-modern"
            />
          </div>
        </div>
      )

    case 'notification':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Channel</label>
            <select
              value={(cfg.channel as string) || 'email'}
              onChange={(e) => onPatchConfig({ channel: e.target.value })}
              className="input-modern w-full"
            >
              {['email', 'sms', 'whatsapp', 'slack', 'webhook', 'in_app'].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Recipients</label>
            <MultiSelectChips
              options={[]}
              selected={(cfg.recipients as string[]) || []}
              onChange={(v) => onPatchConfig({ recipients: v })}
              allowCustom
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Subject</label>
            <input
              value={(cfg.subject as string) || ''}
              onChange={(e) => onPatchConfig({ subject: e.target.value })}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Body</label>
            <textarea
              value={(cfg.body as string) || ''}
              onChange={(e) => onPatchConfig({ body: e.target.value })}
              rows={3}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Priority</label>
            <select
              value={(cfg.priority as string) || 'normal'}
              onChange={(e) => onPatchConfig({ priority: e.target.value })}
              className="input-modern w-full"
            >
              {['low', 'normal', 'high', 'critical'].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        </div>
      )

    case 'decision_gate':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Condition expression
            </label>
            <input
              value={(cfg.condition_expression as string) || ''}
              onChange={(e) => onPatchConfig({ condition_expression: e.target.value })}
              className="input-modern"
              placeholder="len(rows) > 0"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Auto-approve threshold
            </label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={(cfg.auto_approve_threshold as number) ?? 0.95}
              onChange={(e) => onPatchConfig({ auto_approve_threshold: Number(e.target.value) })}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Escalation level
            </label>
            <select
              value={(cfg.escalation_level as string) || 'l1_operator'}
              onChange={(e) => onPatchConfig({ escalation_level: e.target.value })}
              className="input-modern w-full"
            >
              {['l1_operator', 'l2_engineer', 'l3_architect', 'executive'].map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-surface-700 dark:text-surface-300">
            <input
              type="checkbox"
              checked={(cfg.require_human_approval as boolean) ?? false}
              onChange={(e) => onPatchConfig({ require_human_approval: e.target.checked })}
            />
            Require human approval
          </label>
        </div>
      )

    case 'wait':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Duration (ms)
            </label>
            <input
              type="number"
              min={0}
              value={(cfg.duration_ms as number) ?? 0}
              onChange={(e) => onPatchConfig({ duration_ms: Number(e.target.value) })}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Polling condition (optional)
            </label>
            <input
              value={(cfg.condition as string) || ''}
              onChange={(e) => onPatchConfig({ condition: e.target.value })}
              className="input-modern"
            />
          </div>
        </div>
      )

    case 'parallel':
      return (
        <div className="space-y-3">
          <MultiSelectChips
            label="Branches"
            options={[]}
            selected={(cfg.branches as string[]) || []}
            onChange={(v) => onPatchConfig({ branches: v })}
            allowCustom
          />
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Join strategy
            </label>
            <select
              value={(cfg.join_strategy as string) || 'all'}
              onChange={(e) => onPatchConfig({ join_strategy: e.target.value })}
              className="input-modern w-full"
            >
              {['all', 'any', 'first', 'custom'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Max concurrency
            </label>
            <input
              type="number"
              min={1}
              max={16}
              value={(cfg.max_concurrency as number) ?? 4}
              onChange={(e) => onPatchConfig({ max_concurrency: Number(e.target.value) })}
              className="input-modern"
            />
          </div>
        </div>
      )

    case 'subflow':
      return (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Workflow name
            </label>
            <input
              value={(cfg.workflow_name as string) || ''}
              onChange={(e) => onPatchConfig({ workflow_name: e.target.value })}
              className="input-modern"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
              Workflow version (optional)
            </label>
            <input
              value={(cfg.workflow_version as string) || ''}
              onChange={(e) => onPatchConfig({ workflow_version: e.target.value })}
              className="input-modern"
            />
          </div>
          <KeyValueEditor
            label="Input mapping"
            value={(cfg.input_mapping as Record<string, string>) || {}}
            onChange={(v) => onPatchConfig({ input_mapping: v })}
          />
          <KeyValueEditor
            label="Output mapping"
            value={(cfg.output_mapping as Record<string, string>) || {}}
            onChange={(v) => onPatchConfig({ output_mapping: v })}
          />
        </div>
      )

    default:
      return (
        <JsonEditor
          label="Config (JSON)"
          value={cfg}
          onChange={(v) => onPatchConfig(v as Record<string, unknown>)}
        />
      )
  }
}
