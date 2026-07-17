# Validation Workflow Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a visual, detailed UI builder for CarbonVerify's Workflow Validation Engine, allowing operators to create, edit, clone, test, and manage validation workflows without writing JSON.

**Architecture:** Add TypeScript types, React Query hooks, reusable editor components, and three new page components (list, builder, runs) under `/validation-workflows`. The builder uses a three-pane layout: step palette, form-first step list with live SVG graph preview, and per-step/global configuration panel. Phase 1 keeps dependencies minimal; Phase 2 can upgrade the preview to an interactive `@xyflow/react` canvas.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query v5, Axios, Zustand (optional local store), Lucide icons, Vitest.

## Global Constraints

- All new files live under `frontend/src/` and follow the existing directory conventions (`pages/`, `components/validation-workflow-builder/`, `hooks/`, `types/`, `lib/`).
- All API calls go through `frontend/src/services/api.ts`.
- New routes are operator-protected (`requiredRole="operator"`) and added to the Core sidebar group in `Layout.tsx`.
- Every workflow graph is saved through the existing `POST /validation/workflows` and `PATCH /validation/workflows/:id` endpoints; no backend changes.
- Client-side validation must mirror the backend Pydantic rules (unique slug-like step IDs, valid `next_on_*` refs, required fields, numeric bounds).
- No new runtime dependencies in Phase 1.
- Code-split the new pages with `React.lazy` in `App.tsx`.
- All new components must support light and dark mode using existing `surface-*` and `primary-*` tokens.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `frontend/src/types/index.ts` | Append validation workflow/run/actor types |
| `frontend/src/hooks/useValidationWorkflows.ts` | React Query hooks for workflows, runs, actors |
| `frontend/src/lib/validationWorkflowTemplates.ts` | Static workflow template JSON |
| `frontend/src/components/validation-workflow-builder/JsonEditor.tsx` | JSON textarea with parse validation |
| `frontend/src/components/validation-workflow-builder/KeyValueEditor.tsx` | Key/value editor for headers/params/mappings |
| `frontend/src/components/validation-workflow-builder/MultiSelectChips.tsx` | Multi-select of step IDs or tags |
| `frontend/src/components/validation-workflow-builder/ValidationIssuesPanel.tsx` | List of graph validation errors/warnings |
| `frontend/src/components/validation-workflow-builder/StepPalette.tsx` | Step type chips and template gallery |
| `frontend/src/components/validation-workflow-builder/StepList.tsx` | Ordered list of steps with add/remove/reorder |
| `frontend/src/components/validation-workflow-builder/GraphPreview.tsx` | SVG preview of nodes and edges |
| `frontend/src/components/validation-workflow-builder/WorkflowSettingsPanel.tsx` | Workflow name/version/SLA/global policies |
| `frontend/src/components/validation-workflow-builder/StepConfigPanel.tsx` | Per-step configuration form |
| `frontend/src/components/validation-workflow-builder/RunWorkflowPanel.tsx` | Test-run trigger panel |
| `frontend/src/components/validation-workflow-builder/WorkflowRunDetail.tsx` | Run overview/steps/proofs/transitions tabs |
| `frontend/src/pages/ValidationWorkflowListPage.tsx` | Workflow list page |
| `frontend/src/pages/ValidationWorkflowBuilderPage.tsx` | Builder page |
| `frontend/src/pages/ValidationWorkflowRunsPage.tsx` | Run history page |
| `frontend/src/App.tsx` | Add lazy-loaded routes |
| `frontend/src/components/Layout.tsx` | Add sidebar nav item |
| `frontend/src/test/ValidationWorkflowBuilderPage.test.tsx` | Component tests |
| `docs/WORKFLOW_VALIDATION_ENGINE.md` | Add UI builder section |
| `CHANGELOG.md` | Add feature entry |

---

### Task 0: Expose `workflow_graph` in the workflow API response

**Files:**
- Modify: `backend/app/validation_engine/schemas.py`
- Modify: `backend/app/api/validation_engine.py`

**Interfaces:**
- Consumes: existing `WorkflowResponse` schema and API route file
- Produces: `WorkflowResponse` now includes `workflow_graph`; all route constructors pass it through

- [ ] **Step 1: Add `workflow_graph` to `WorkflowResponse`**

In `backend/app/validation_engine/schemas.py`, add the field:

```python
class WorkflowResponse(BaseModel):
    id: str
    name: str
    version: str
    description: Optional[str]
    active: bool
    graph_hash: str
    workflow_graph: Dict[str, Any]   # <-- add this line
    sla_seconds: Optional[int]
    human_gates_required: bool
    created_at: str
    updated_at: str
```

- [ ] **Step 2: Pass the graph through in all route responses**

In `backend/app/api/validation_engine.py`, locate every `WorkflowResponse(...)` construction and add `workflow_graph=workflow.workflow_graph`. There are four occurrences (create, list, get, patch). For list, use `w.workflow_graph`.

Example for `get_workflow`:

```python
return WorkflowResponse(
    id=str(workflow.id),
    name=workflow.name,
    version=workflow.version,
    description=workflow.description,
    active=workflow.active,
    graph_hash=workflow.graph_hash,
    workflow_graph=workflow.workflow_graph,
    sla_seconds=workflow.sla_seconds,
    human_gates_required=workflow.human_gates_required,
    created_at=workflow.created_at.isoformat(),
    updated_at=workflow.updated_at.isoformat(),
)
```

- [ ] **Step 3: Run backend tests**

```bash
cd /Users/lukeouko/carbonverify/backend
source .venv/bin/activate
pytest tests/test_validation_engine.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add backend/app/validation_engine/schemas.py backend/app/api/validation_engine.py
git commit -m "feat(validation-workflow-builder): include workflow_graph in API responses"
```

---

### Task 1: Add validation-engine TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- Consumes: none
- Produces: `WorkflowStepType`, `RetryPolicy`, `CircuitBreakerConfig`, `WorkflowStep`, `WorkflowGraph`, `ValidationWorkflow`, `ValidationWorkflowCreatePayload`, `ValidationWorkflowUpdatePayload`, `ValidationRun`, `RunTriggerPayload`, `StepExecution`, `ValidationProof`, `ValidationTransition`, `SyntheticActor`

**Interfaces:**
- Consumes: none
- Produces: `WorkflowStepType`, `RetryPolicy`, `CircuitBreakerConfig`, `WorkflowStep`, `WorkflowGraph`, `ValidationWorkflow`, `ValidationWorkflowCreatePayload`, `ValidationWorkflowUpdatePayload`, `ValidationRun`, `RunTriggerPayload`, `StepExecution`, `ValidationProof`, `ValidationTransition`, `SyntheticActor`

- [ ] **Step 1: Append types to `frontend/src/types/index.ts`**

```typescript
export type WorkflowStepType =
  | 'http_request'
  | 'database_query'
  | 'service_call'
  | 'external_api'
  | 'notification'
  | 'dom_capture'
  | 'decision_gate'
  | 'ai_evaluation'
  | 'wait'
  | 'parallel'
  | 'subflow'

export interface RetryPolicy {
  max_retries: number
  backoff_multiplier: number
  initial_delay_ms: number
  retry_on: string[]
}

export interface CircuitBreakerConfig {
  failure_threshold: number
  recovery_timeout_ms: number
  half_open_max_calls: number
}

export interface WorkflowStep {
  id: string
  name: string
  type: WorkflowStepType
  description?: string
  enabled: boolean
  config: Record<string, unknown>
  retry_policy?: RetryPolicy
  next_on_success: string[]
  next_on_failure: string[]
  timeout_ms: number
  capture_proof: boolean
  checkpoint: boolean
  skippable: boolean
}

export interface WorkflowGraph {
  version: string
  description?: string
  entry_step: string
  retry_policy: RetryPolicy
  circuit_breaker: CircuitBreakerConfig
  steps: WorkflowStep[]
  variables: Record<string, unknown>
  human_gates_required: boolean
  sla_seconds?: number
}

export interface ValidationWorkflow {
  id: string
  name: string
  version: string
  description?: string
  active: boolean
  graph_hash: string
  workflow_graph: WorkflowGraph
  sla_seconds?: number
  human_gates_required: boolean
  created_at: string
  updated_at: string
}

export interface ValidationWorkflowCreatePayload {
  name: string
  version?: string
  description?: string
  workflow_graph: WorkflowGraph
  sla_seconds?: number
  human_gates_required?: boolean
}

export interface ValidationWorkflowUpdatePayload {
  description?: string
  active?: boolean
  workflow_graph?: WorkflowGraph
  sla_seconds?: number
  human_gates_required?: boolean
}

export interface ValidationRun {
  id: string
  workflow_id: string
  project_id?: string
  status: string
  trigger_event: string
  confidence_score?: number
  merkle_root?: string
  radix_tx_ref?: string
  started_at?: string
  completed_at?: string
  created_at: string
  error_message?: string
  remediation_count: number
  human_intervened: boolean
  awaiting_human_decision: boolean
}

export interface RunTriggerPayload {
  workflow_id: string
  project_id?: string
  trigger_event?: string
  input_data?: Record<string, unknown>
}

export interface StepExecution {
  id: string
  step_id: string
  step_index: number
  step_type: WorkflowStepType
  step_name: string
  status: string
  step_hash?: string
  duration_ms?: number
  retry_count: number
  error_message?: string
  started_at?: string
  completed_at?: string
}

export interface ValidationProof {
  id: string
  step_execution_id?: string
  proof_type: string
  proof_hash: string
  merkle_leaf_index?: number
  captured_at: string
}

export interface ValidationTransition {
  id: string
  from_state: string
  to_state: string
  actor_type: string
  reason?: string
  transition_hash: string
  previous_hash?: string
  occurred_at: string
}

export interface SyntheticActor {
  id: string
  name: string
  actor_type: string
  profile_key: string
  markers: Record<string, unknown>
  behavior_config: Record<string, unknown>
  context_data: Record<string, unknown>
  active: boolean
  usage_count: number
  created_at: string
  last_used_at?: string
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no new errors from the appended types.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/types/index.ts
git commit -m "feat(validation-workflow-builder): add workflow/run/actor types"
```

---

### Task 2: Add React Query hooks

**Files:**
- Create: `frontend/src/hooks/useValidationWorkflows.ts`

**Interfaces:**
- Consumes: types from Task 1, `api` client
- Produces: `useWorkflows`, `useWorkflow`, `useCreateWorkflow`, `useUpdateWorkflow`, `useToggleWorkflowActive`, `useValidationRuns`, `useValidationRun`, `useTriggerRun`, `useCancelRun`, `useStepExecutions`, `useProofs`, `useTransitions`, `useSyntheticActors`

- [ ] **Step 1: Create the hooks file**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import type {
  ValidationWorkflow,
  ValidationWorkflowCreatePayload,
  ValidationWorkflowUpdatePayload,
  ValidationRun,
  RunTriggerPayload,
  StepExecution,
  ValidationProof,
  ValidationTransition,
  SyntheticActor,
} from '../types'

const WORKFLOWS_KEY = ['validation-workflows']
const workflowKey = (id: string) => ['validation-workflows', id]
const runsKey = (workflowId: string) => ['validation-runs', workflowId]
const runKey = (runId: string) => ['validation-run', runId]
const actorsKey = ['synthetic-actors']

export function useWorkflows() {
  return useQuery<ValidationWorkflow[]>({
    queryKey: WORKFLOWS_KEY,
    queryFn: async () => {
      const res = await api.get('/validation/workflows')
      return res.data
    },
  })
}

export function useWorkflow(id: string | undefined) {
  return useQuery<ValidationWorkflow>({
    queryKey: workflowKey(id || ''),
    queryFn: async () => {
      const res = await api.get(`/validation/workflows/${id}`)
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateWorkflow() {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, ValidationWorkflowCreatePayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/validation/workflows', payload)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: WORKFLOWS_KEY }),
  })
}

export function useUpdateWorkflow(id: string) {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, ValidationWorkflowUpdatePayload>({
    mutationFn: async (payload) => {
      const res = await api.patch(`/validation/workflows/${id}`, payload)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey(id) })
      qc.invalidateQueries({ queryKey: WORKFLOWS_KEY })
    },
  })
}

export function useToggleWorkflowActive(id: string) {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, boolean>({
    mutationFn: async (active) => {
      const res = await api.patch(`/validation/workflows/${id}`, { active })
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey(id) })
      qc.invalidateQueries({ queryKey: WORKFLOWS_KEY })
    },
  })
}

export function useValidationRuns(workflowId: string | undefined) {
  return useQuery<ValidationRun[]>({
    queryKey: runsKey(workflowId || ''),
    queryFn: async () => {
      const res = await api.get('/validation/runs', { params: { workflow_id: workflowId } })
      return res.data
    },
    enabled: !!workflowId,
  })
}

export function useValidationRun(runId: string | undefined) {
  return useQuery<ValidationRun>({
    queryKey: runKey(runId || ''),
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}`)
      return res.data
    },
    enabled: !!runId,
    refetchInterval: (data) =>
      data && !['completed', 'failed', 'archived'].includes(data.status) ? 2000 : false,
  })
}

export function useTriggerRun() {
  const qc = useQueryClient()
  return useMutation<ValidationRun, unknown, RunTriggerPayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/validation/runs', payload)
      return res.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: runsKey(data.workflow_id) })
    },
  })
}

export function useCancelRun() {
  const qc = useQueryClient()
  return useMutation<ValidationRun, unknown, string>({
    mutationFn: async (runId) => {
      const res = await api.post(`/validation/runs/${runId}/cancel`)
      return res.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: runKey(data.id) })
      qc.invalidateQueries({ queryKey: runsKey(data.workflow_id) })
    },
  })
}

export function useStepExecutions(runId: string | undefined) {
  return useQuery<StepExecution[]>({
    queryKey: ['validation-run-steps', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/steps`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useProofs(runId: string | undefined) {
  return useQuery<ValidationProof[]>({
    queryKey: ['validation-run-proofs', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/proofs`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useTransitions(runId: string | undefined) {
  return useQuery<ValidationTransition[]>({
    queryKey: ['validation-run-transitions', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/transitions`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useSyntheticActors() {
  return useQuery<SyntheticActor[]>({
    queryKey: actorsKey,
    queryFn: async () => {
      const res = await api.get('/validation/synthetic-actors')
      return res.data
    },
  })
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/hooks/useValidationWorkflows.ts
git commit -m "feat(validation-workflow-builder): add workflow/run react-query hooks"
```

---

### Task 3: Add workflow templates library

**Files:**
- Create: `frontend/src/lib/validationWorkflowTemplates.ts`

**Interfaces:**
- Consumes: `WorkflowGraph` type
- Produces: `WORKFLOW_TEMPLATES` array, `loadWorkflowTemplate(name)` helper

- [ ] **Step 1: Create the templates file**

```typescript
import type { WorkflowGraph } from '../types'

export interface WorkflowTemplate {
  name: string
  description: string
  graph: WorkflowGraph
}

const defaultRetryPolicy = {
  max_retries: 3,
  backoff_multiplier: 2,
  initial_delay_ms: 500,
  retry_on: ['timeout', 'connection_error', 'rate_limit'],
}

const defaultCircuitBreaker = {
  failure_threshold: 5,
  recovery_timeout_ms: 30000,
  half_open_max_calls: 3,
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    name: 'Document quality gate',
    description: 'Score project documentation with AI and notify on failure.',
    graph: {
      version: '1.0',
      description: 'AI-led documentation quality gate',
      entry_step: 'evaluate_docs',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'evaluate_docs',
          name: 'Evaluate documentation',
          type: 'ai_evaluation',
          enabled: true,
          config: {
            prompt:
              'Rate the completeness and clarity of the project documentation on a scale of 0.0 to 1.0. Return score, passed, reasoning, and recommendation.',
            input_data: { document_summary: '${document_summary}' },
            pass_threshold: 0.75,
            fail_on_error: true,
            temperature: 0.2,
            max_tokens: 1024,
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_team'],
          timeout_ms: 60000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_team',
          name: 'Notify team',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Documentation quality gate failed',
            body: 'The AI evaluation step failed. Please review the project documentation.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { document_summary: '' },
      human_gates_required: false,
    },
  },
  {
    name: 'Data source completeness check',
    description: 'Verify expected data rows exist and flag missing data.',
    graph: {
      version: '1.0',
      description: 'Check that required data sources have expected row counts',
      entry_step: 'count_rows',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'count_rows',
          name: 'Count data rows',
          type: 'database_query',
          enabled: true,
          config: {
            query: 'SELECT COUNT(*) FROM data_sources WHERE project_id = :project_id',
            params: { project_id: '${project_id}' },
            expected_row_count: null,
            snapshot_result: true,
          },
          next_on_success: ['check_threshold'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'check_threshold',
          name: 'Check row threshold',
          type: 'decision_gate',
          enabled: true,
          config: {
            condition_expression: 'len(rows) >= 1',
            require_human_approval: false,
            auto_approve_threshold: 0.95,
            timeout_seconds: 300,
            escalation_level: 'l1_operator',
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_missing_data'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_missing_data',
          name: 'Notify missing data',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Missing data sources',
            body: 'The project does not have any registered data sources.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { project_id: '' },
      human_gates_required: false,
    },
  },
  {
    name: 'HTTP health check + notify',
    description: 'Ping an endpoint and send a notification on failure.',
    graph: {
      version: '1.0',
      description: 'HTTP health check with failure notification',
      entry_step: 'ping_endpoint',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'ping_endpoint',
          name: 'Ping endpoint',
          type: 'http_request',
          enabled: true,
          config: {
            method: 'GET',
            url: '${health_url}',
            headers: {},
            body: null,
            timeout_ms: 10000,
            expected_status_codes: [200],
            capture_response: true,
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_failure'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_failure',
          name: 'Notify failure',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Health check failed',
            body: 'The health check endpoint did not return 200.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { health_url: 'https://example.com/health' },
      human_gates_required: false,
    },
  },
]

export function loadWorkflowTemplate(name: string): WorkflowGraph | undefined {
  return WORKFLOW_TEMPLATES.find((t) => t.name === name)?.graph
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/lib/validationWorkflowTemplates.ts
git commit -m "feat(validation-workflow-builder): add workflow template library"
```

---

### Task 4: Add reusable editor components

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/JsonEditor.tsx`
- Create: `frontend/src/components/validation-workflow-builder/KeyValueEditor.tsx`
- Create: `frontend/src/components/validation-workflow-builder/MultiSelectChips.tsx`

**Interfaces:**
- Consumes: none
- Produces: `JsonEditor`, `KeyValueEditor`, `MultiSelectChips` components

- [ ] **Step 1: Create `JsonEditor.tsx`**

```typescript
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
```

- [ ] **Step 2: Create `KeyValueEditor.tsx`**

```typescript
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
```

- [ ] **Step 3: Create `MultiSelectChips.tsx`**

```typescript
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
```

- [ ] **Step 4: Verify TypeScript and lint**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
npm run lint -- --no-error-on-unmatched-pattern src/components/validation-workflow-builder/JsonEditor.tsx src/components/validation-workflow-builder/KeyValueEditor.tsx src/components/validation-workflow-builder/MultiSelectChips.tsx
```

Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/JsonEditor.tsx frontend/src/components/validation-workflow-builder/KeyValueEditor.tsx frontend/src/components/validation-workflow-builder/MultiSelectChips.tsx
git commit -m "feat(validation-workflow-builder): add reusable editor components"
```

---

### Task 5: Add `ValidationIssuesPanel`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/ValidationIssuesPanel.tsx`

**Interfaces:**
- Consumes: `ValidationIssue` type (local)
- Produces: `ValidationIssuesPanel` component

- [ ] **Step 1: Create the component**

```typescript
import { AlertTriangle, XCircle } from 'lucide-react'

export interface ValidationIssue {
  type: 'error' | 'warning'
  message: string
  stepId?: string
}

interface ValidationIssuesPanelProps {
  issues: ValidationIssue[]
}

export function ValidationIssuesPanel({ issues }: ValidationIssuesPanelProps) {
  if (issues.length === 0) return null
  const errors = issues.filter((i) => i.type === 'error')
  const warnings = issues.filter((i) => i.type === 'warning')

  return (
    <div className="card border-l-4 border-l-amber-500 p-4 mb-4">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-amber-500" />
        <h3 className="font-semibold text-sm text-surface-900 dark:text-surface-100">
          {errors.length} error{errors.length !== 1 ? 's' : ''}, {warnings.length} warning
          {warnings.length !== 1 ? 's' : ''}
        </h3>
      </div>
      <ul className="space-y-1">
        {issues.map((issue, idx) => (
          <li key={idx} className="flex items-start gap-2 text-xs">
            {issue.type === 'error' ? (
              <XCircle className="w-4 h-4 text-red-500 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
            )}
            <span className="text-surface-700 dark:text-surface-300">
              {issue.stepId ? `[${issue.stepId}] ` : ''}
              {issue.message}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/ValidationIssuesPanel.tsx
git commit -m "feat(validation-workflow-builder): add validation issues panel"
```

---

### Task 6: Add `StepPalette`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/StepPalette.tsx`

**Interfaces:**
- Consumes: `WorkflowStepType`, `WORKFLOW_TEMPLATES`
- Produces: `StepPalette` component

- [ ] **Step 1: Create the component**

```typescript
import { Plus, GitBranch, Database, PhoneCall, Globe, Mail, Camera, BrainCircuit, Timer, Layers, Subtitles } from 'lucide-react'
import type { WorkflowStepType } from '../../types'
import { WORKFLOW_TEMPLATES } from '../../lib/validationWorkflowTemplates'

const STEP_TYPES: { type: WorkflowStepType; label: string; icon: React.ElementType }[] = [
  { type: 'http_request', label: 'HTTP Request', icon: Globe },
  { type: 'database_query', label: 'DB Query', icon: Database },
  { type: 'service_call', label: 'Service Call', icon: PhoneCall },
  { type: 'external_api', label: 'External API', icon: Globe },
  { type: 'notification', label: 'Notification', icon: Mail },
  { type: 'dom_capture', label: 'DOM Capture', icon: Camera },
  { type: 'decision_gate', label: 'Decision Gate', icon: GitBranch },
  { type: 'ai_evaluation', label: 'AI Evaluation', icon: BrainCircuit },
  { type: 'wait', label: 'Wait', icon: Timer },
  { type: 'parallel', label: 'Parallel', icon: Layers },
  { type: 'subflow', label: 'Subflow', icon: Subtitles },
]

interface StepPaletteProps {
  onAddStep: (type: WorkflowStepType) => void
  onLoadTemplate: (name: string) => void
}

export function StepPalette({ onAddStep, onLoadTemplate }: StepPaletteProps) {
  return (
    <div className="space-y-6 p-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
          Step Types
        </h3>
        <div className="grid grid-cols-1 gap-2">
          {STEP_TYPES.map(({ type, label, icon: Icon }) => (
            <button
              key={type}
              type="button"
              onClick={() => onAddStep(type)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 hover:border-primary-300 dark:hover:border-primary-700 transition-colors text-left"
            >
              <Icon className="w-4 h-4 text-surface-500 dark:text-surface-400" />
              <span className="text-sm text-surface-700 dark:text-surface-300">{label}</span>
              <Plus className="w-3 h-3 ml-auto text-surface-400" />
            </button>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
          Templates
        </h3>
        <div className="space-y-2">
          {WORKFLOW_TEMPLATES.map((template) => (
            <button
              key={template.name}
              type="button"
              onClick={() => onLoadTemplate(template.name)}
              className="w-full text-left px-3 py-2 rounded-lg border border-dashed border-surface-300 dark:border-surface-600 hover:border-primary-400 dark:hover:border-primary-600 transition-colors"
            >
              <p className="text-sm font-medium text-surface-800 dark:text-surface-200">{template.name}</p>
              <p className="text-xs text-surface-500 dark:text-surface-400">{template.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/StepPalette.tsx
git commit -m "feat(validation-workflow-builder): add step palette component"
```

---

### Task 7: Add `StepList`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/StepList.tsx`

**Interfaces:**
- Consumes: `WorkflowStep`
- Produces: `StepList` component

- [ ] **Step 1: Create the component**

```typescript
import { Trash2, GripVertical } from 'lucide-react'
import type { WorkflowStep } from '../../types'

interface StepListProps {
  steps: WorkflowStep[]
  selectedId: string | null
  entryStep: string
  onSelect: (id: string) => void
  onRemove: (id: string) => void
  onMove: (fromIndex: number, toIndex: number) => void
}

export function StepList({ steps, selectedId, entryStep, onSelect, onRemove, onMove }: StepListProps) {
  return (
    <div className="space-y-2 p-4">
      {steps.map((step, index) => (
        <div
          key={step.id}
          onClick={() => onSelect(step.id)}
          className={`group flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
            selectedId === step.id
              ? 'border-primary-400 bg-primary-50/50 dark:border-primary-500/50 dark:bg-primary-950/10'
              : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900 hover:border-primary-200 dark:hover:border-primary-800'
          }`}
        >
          <button
            type="button"
            className="text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 cursor-grab"
            onClick={(e) => {
              e.stopPropagation()
              if (index > 0) onMove(index, index - 1)
            }}
            aria-label="Move up"
          >
            <GripVertical className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-surface-500 dark:text-surface-400">{step.id}</span>
              {step.id === entryStep && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200">
                  entry
                </span>
              )}
              {!step.enabled && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400">
                  disabled
                </span>
              )}
            </div>
            <p className="text-sm font-medium text-surface-800 dark:text-surface-200 truncate">{step.name}</p>
            <p className="text-xs text-surface-500 dark:text-surface-400">{step.type}</p>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onRemove(step.id)
            }}
            className="opacity-0 group-hover:opacity-100 text-surface-400 hover:text-red-500 transition-opacity"
            aria-label="Remove step"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
      {steps.length === 0 && (
        <p className="text-sm text-surface-500 dark:text-surface-400 text-center py-8">
          No steps yet. Add one from the palette.
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/StepList.tsx
git commit -m "feat(validation-workflow-builder): add step list component"
```

---

### Task 8: Add `GraphPreview`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/GraphPreview.tsx`

**Interfaces:**
- Consumes: `WorkflowGraph`
- Produces: `GraphPreview` SVG component

- [ ] **Step 1: Create the component**

```typescript
import type { WorkflowGraph } from '../../types'

interface GraphPreviewProps {
  graph: WorkflowGraph
}

export function GraphPreview({ graph }: GraphPreviewProps) {
  const nodeHeight = 36
  const nodeGap = 56
  const width = 600
  const height = Math.max(120, graph.steps.length * (nodeHeight + nodeGap) + 40)
  const centerX = width / 2

  const nodeY = (index: number) => 30 + index * (nodeHeight + nodeGap)

  const stepIndex = new Map(graph.steps.map((s, i) => [s.id, i]))

  return (
    <div className="p-4 overflow-auto">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-surface-500 dark:text-surface-400 mb-3">
        Graph Preview
      </h3>
      <svg width={width} height={height} className="bg-surface-50 dark:bg-surface-900/50 rounded-lg border border-surface-200 dark:border-surface-700">
        {graph.steps.map((step, index) => {
          const y = nodeY(index)
          return (
            <g key={step.id}>
              <rect
                x={centerX - 90}
                y={y}
                width={180}
                height={nodeHeight}
                rx={6}
                className={`${
                  step.id === graph.entry_step
                    ? 'fill-primary-100 stroke-primary-500 dark:fill-primary-950 dark:stroke-primary-500'
                    : 'fill-white stroke-surface-300 dark:fill-surface-800 dark:stroke-surface-600'
                }`}
                strokeWidth={step.id === graph.entry_step ? 2 : 1}
              />
              <text
                x={centerX}
                y={y + 22}
                textAnchor="middle"
                className="text-xs fill-surface-800 dark:fill-surface-200"
              >
                {step.id}
              </text>
            </g>
          )
        })}

        {graph.steps.map((step, index) => {
          const fromY = nodeY(index) + nodeHeight
          const targets = [...step.next_on_success, ...step.next_on_failure]
          return targets.map((targetId, tidx) => {
            const targetIndex = stepIndex.get(targetId)
            if (targetIndex === undefined) return null
            const toY = nodeY(targetIndex)
            const isFailure = tidx >= step.next_on_success.length
            return (
              <path
                key={`${step.id}-${targetId}-${tidx}`}
                d={`M ${centerX} ${fromY} L ${centerX} ${toY - 4}`}
                markerEnd="url(#arrow)"
                fill="none"
                className={isFailure ? 'stroke-red-400 stroke-dashed' : 'stroke-surface-400'}
                strokeWidth={1.5}
                strokeDasharray={isFailure ? '4 4' : undefined}
              />
            )
          })
        })}

        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" className="fill-surface-400" />
          </marker>
        </defs>
      </svg>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/GraphPreview.tsx
git commit -m "feat(validation-workflow-builder): add graph preview component"
```

---

### Task 9: Add `WorkflowSettingsPanel`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/WorkflowSettingsPanel.tsx`

**Interfaces:**
- Consumes: `WorkflowGraph`, `ValidationWorkflowCreatePayload` fields
- Produces: `WorkflowSettingsPanel` component

- [ ] **Step 1: Create the component**

```typescript
import { JsonEditor } from './JsonEditor'
import type { WorkflowGraph } from '../../types'

interface WorkflowSettingsPanelProps {
  name: string
  version: string
  description: string
  graph: WorkflowGraph
  onChangeName: (name: string) => void
  onChangeVersion: (version: string) => void
  onChangeDescription: (description: string) => void
  onChangeGraph: (graph: WorkflowGraph) => void
}

export function WorkflowSettingsPanel({
  name,
  version,
  description,
  graph,
  onChangeName,
  onChangeVersion,
  onChangeDescription,
  onChangeGraph,
}: WorkflowSettingsPanelProps) {
  return (
    <div className="p-4 space-y-4">
      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Workflow Settings</h3>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Name</label>
        <input value={name} onChange={(e) => onChangeName(e.target.value)} className="input-modern" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Version</label>
        <input value={version} onChange={(e) => onChangeVersion(e.target.value)} className="input-modern" />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => onChangeDescription(e.target.value)}
          rows={3}
          className="input-modern"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Entry Step</label>
        <select
          value={graph.entry_step}
          onChange={(e) => onChangeGraph({ ...graph, entry_step: e.target.value })}
          className="input-modern w-full"
        >
          {graph.steps.map((s) => (
            <option key={s.id} value={s.id}>
              {s.id}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">
          SLA Seconds (optional)
        </label>
        <input
          type="number"
          value={graph.sla_seconds || ''}
          onChange={(e) => onChangeGraph({ ...graph, sla_seconds: e.target.value ? Number(e.target.value) : undefined })}
          className="input-modern"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="human-gates"
          type="checkbox"
          checked={graph.human_gates_required}
          onChange={(e) => onChangeGraph({ ...graph, human_gates_required: e.target.checked })}
          className="rounded border-surface-300"
        />
        <label htmlFor="human-gates" className="text-sm text-surface-700 dark:text-surface-300">
          Require human approval at decision gates by default
        </label>
      </div>

      <JsonEditor
        label="Global Variables"
        value={graph.variables}
        onChange={(variables) => onChangeGraph({ ...graph, variables })}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/WorkflowSettingsPanel.tsx
git commit -m "feat(validation-workflow-builder): add workflow settings panel"
```

---

### Task 10: Add `StepConfigPanel`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/StepConfigPanel.tsx`

**Interfaces:**
- Consumes: `WorkflowStep`, `WorkflowGraph`, update callbacks
- Produces: `StepConfigPanel` component

- [ ] **Step 1: Create the component**

This is a large component. The file contains one main exported component and helper sub-components for each step type. Keep it in one file for the plan; split later if it grows unwieldy.

Key skeleton:

```typescript
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
          onChange={(v) => onPatchConfig(v)}
        />
      )
  }
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/StepConfigPanel.tsx
git commit -m "feat(validation-workflow-builder): add step config panel"
```

---

### Task 11: Add `RunWorkflowPanel`

**Files:**
- Create: `frontend/src/components/validation-workflow-builder/RunWorkflowPanel.tsx`

**Interfaces:**
- Consumes: `ValidationWorkflow`, `useProjects` hook (or existing project list), `useTriggerRun`
- Produces: `RunWorkflowPanel` component

- [ ] **Step 1: Create the component**

```typescript
import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { JsonEditor } from './JsonEditor'
import { useProjects } from '../../hooks/useProjects'
import { useTriggerRun } from '../../hooks/useValidationWorkflows'
import type { ValidationWorkflow, ValidationRun } from '../../types'

interface RunWorkflowPanelProps {
  workflow: ValidationWorkflow
  onRunCreated: (run: ValidationRun) => void
}

export function RunWorkflowPanel({ workflow, onRunCreated }: RunWorkflowPanelProps) {
  const { data: projects } = useProjects()
  const trigger = useTriggerRun()
  const [projectId, setProjectId] = useState('')
  const [triggerEvent, setTriggerEvent] = useState('manual_test')
  const [inputData, setInputData] = useState<Record<string, unknown>>({})

  const handleRun = async () => {
    const run = await trigger.mutateAsync({
      workflow_id: workflow.id,
      project_id: projectId || undefined,
      trigger_event: triggerEvent,
      input_data: inputData,
    })
    onRunCreated(run)
  }

  return (
    <div className="p-4 space-y-4 border-t border-surface-200 dark:border-surface-700">
      <h3 className="text-sm font-semibold text-surface-900 dark:text-surface-100">Test Run</h3>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Project (optional)</label>
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="input-modern w-full">
          <option value="">— None —</option>
          {projects?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-surface-600 dark:text-surface-400 mb-1">Trigger event</label>
        <input value={triggerEvent} onChange={(e) => setTriggerEvent(e.target.value)} className="input-modern" />
      </div>

      <JsonEditor label="Input data" value={inputData} onChange={setInputData} />

      <button
        type="button"
        onClick={handleRun}
        disabled={trigger.isPending}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {trigger.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
        Run workflow
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors. If `useProjects` does not exist, create a minimal one in `frontend/src/hooks/useProjects.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import api from '../services/api'
import type { Project } from '../types'

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await api.get('/projects')
      return res.data
    },
  })
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/RunWorkflowPanel.tsx
git commit -m "feat(validation-workflow-builder): add test-run panel"
```

---

### Task 12: Add graph validation utility

**Files:**
- Create: `frontend/src/lib/validationWorkflowGraph.ts`

**Interfaces:**
- Consumes: `WorkflowGraph`
- Produces: `validateWorkflowGraph(graph)` returning `ValidationIssue[]`

- [ ] **Step 1: Create the utility**

```typescript
import type { WorkflowGraph, WorkflowStep } from '../types'
import type { ValidationIssue } from '../components/validation-workflow-builder/ValidationIssuesPanel'

const ID_PATTERN = /^[a-zA-Z0-9_\-]+$/

export function validateWorkflowGraph(graph: WorkflowGraph): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const stepIds = new Set<string>()
  const duplicates = new Set<string>()

  graph.steps.forEach((step) => {
    if (stepIds.has(step.id)) {
      duplicates.add(step.id)
    } else {
      stepIds.add(step.id)
    }
  })

  duplicates.forEach((id) => issues.push({ type: 'error', message: `Step ID "${id}" is used more than once.` }))

  graph.steps.forEach((step) => {
    if (!step.id) issues.push({ type: 'error', message: 'Step ID is required.', stepId: step.id })
    if (!step.name) issues.push({ type: 'error', message: 'Step name is required.', stepId: step.id })
    if (!ID_PATTERN.test(step.id)) {
      issues.push({ type: 'error', message: 'Step ID may only contain letters, numbers, underscores, and hyphens.', stepId: step.id })
    }
    if (step.timeout_ms < 1000) {
      issues.push({ type: 'error', message: 'Timeout must be at least 1000 ms.', stepId: step.id })
    }
  })

  if (!graph.entry_step) {
    issues.push({ type: 'error', message: 'Entry step is required.' })
  } else if (!stepIds.has(graph.entry_step)) {
    issues.push({ type: 'error', message: `Entry step "${graph.entry_step}" does not exist.` })
  }

  graph.steps.forEach((step) => {
    ;[...step.next_on_success, ...step.next_on_failure].forEach((ref) => {
      if (ref !== 'end' && ref !== 'fail' && !stepIds.has(ref)) {
        issues.push({ type: 'error', message: `Reference to unknown step "${ref}".`, stepId: step.id })
      }
    })
  })

  const reachable = new Set<string>()
  const visit = (id: string) => {
    if (reachable.has(id)) return
    reachable.add(id)
    const step = graph.steps.find((s) => s.id === id)
    if (!step) return
    ;[...step.next_on_success, ...step.next_on_failure].forEach((ref) => {
      if (ref !== 'end' && ref !== 'fail') visit(ref)
    })
  }
  if (graph.entry_step && stepIds.has(graph.entry_step)) visit(graph.entry_step)

  graph.steps.forEach((step) => {
    if (!reachable.has(step.id)) {
      issues.push({ type: 'warning', message: `Step "${step.id}" is not reachable from the entry step.`, stepId: step.id })
    }
  })

  validateStepConfig(graph.steps, issues)

  return issues
}

function validateStepConfig(steps: WorkflowStep[], issues: ValidationIssue[]) {
  steps.forEach((step) => {
    const cfg = step.config
    switch (step.type) {
      case 'ai_evaluation': {
        const prompt = cfg.prompt as string | undefined
        if (!prompt || prompt.length < 1) {
          issues.push({ type: 'error', message: 'Prompt is required.', stepId: step.id })
        }
        const threshold = cfg.pass_threshold as number | undefined
        if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
          issues.push({ type: 'error', message: 'Pass threshold must be between 0.0 and 1.0.', stepId: step.id })
        }
        const tokens = cfg.max_tokens as number | undefined
        if (tokens !== undefined && (tokens < 100 || tokens > 8192)) {
          issues.push({ type: 'error', message: 'Max tokens must be between 100 and 8192.', stepId: step.id })
        }
        break
      }
      case 'http_request': {
        if (!cfg.url) issues.push({ type: 'error', message: 'URL is required.', stepId: step.id })
        const method = cfg.method as string
        if (!['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'].includes(method)) {
          issues.push({ type: 'error', message: 'Invalid HTTP method.', stepId: step.id })
        }
        break
      }
      case 'database_query': {
        const query = cfg.query as string
        if (!query) issues.push({ type: 'error', message: 'Query is required.', stepId: step.id })
        else if (!/^\s*SELECT\s/i.test(query)) {
          issues.push({ type: 'error', message: 'Only SELECT queries are allowed.', stepId: step.id })
        }
        break
      }
      case 'decision_gate': {
        if (!cfg.condition_expression) {
          issues.push({ type: 'error', message: 'Condition expression is required.', stepId: step.id })
        }
        break
      }
      case 'wait': {
        const duration = cfg.duration_ms as number
        if (duration === undefined || duration < 0) {
          issues.push({ type: 'error', message: 'Wait duration must be >= 0.', stepId: step.id })
        }
        break
      }
      case 'parallel': {
        const branches = cfg.branches as string[] | undefined
        if (!branches || branches.length < 2) {
          issues.push({ type: 'error', message: 'Parallel step needs at least 2 branches.', stepId: step.id })
        }
        break
      }
      case 'subflow': {
        if (!cfg.workflow_name) issues.push({ type: 'error', message: 'Workflow name is required.', stepId: step.id })
        break
      }
    }
  })
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/lib/validationWorkflowGraph.ts
git commit -m "feat(validation-workflow-builder): add client-side graph validator"
```

---

### Task 13: Add `ValidationWorkflowBuilderPage`

**Files:**
- Create: `frontend/src/pages/ValidationWorkflowBuilderPage.tsx`

**Interfaces:**
- Consumes: all builder components, hooks, templates, validator
- Produces: main builder page

- [ ] **Step 1: Create the page**

The page is large. Implement it with local state and the helpers below:

```typescript
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Save, Play, Loader2, ArrowLeft } from 'lucide-react'
import { StepPalette } from '../components/validation-workflow-builder/StepPalette'
import { StepList } from '../components/validation-workflow-builder/StepList'
import { GraphPreview } from '../components/validation-workflow-builder/GraphPreview'
import { StepConfigPanel } from '../components/validation-workflow-builder/StepConfigPanel'
import { WorkflowSettingsPanel } from '../components/validation-workflow-builder/WorkflowSettingsPanel'
import { RunWorkflowPanel } from '../components/validation-workflow-builder/RunWorkflowPanel'
import { ValidationIssuesPanel } from '../components/validation-workflow-builder/ValidationIssuesPanel'
import { useWorkflow, useCreateWorkflow, useUpdateWorkflow } from '../hooks/useValidationWorkflows'
import { loadWorkflowTemplate } from '../lib/validationWorkflowTemplates'
import { validateWorkflowGraph } from '../lib/validationWorkflowGraph'
import type { WorkflowGraph, WorkflowStep, WorkflowStepType, ValidationWorkflow } from '../types'

const DEFAULT_GRAPH: WorkflowGraph = {
  version: '1.0',
  description: '',
  entry_step: '',
  retry_policy: { max_retries: 3, backoff_multiplier: 2, initial_delay_ms: 500, retry_on: ['timeout', 'connection_error', 'rate_limit'] },
  circuit_breaker: { failure_threshold: 5, recovery_timeout_ms: 30000, half_open_max_calls: 3 },
  steps: [],
  variables: {},
  human_gates_required: false,
}

function makeEmptyStep(type: WorkflowStepType, index: number): WorkflowStep {
  return {
    id: `${type}_${index + 1}`,
    name: `${type} step`,
    type,
    description: '',
    enabled: true,
    config: {},
    next_on_success: [],
    next_on_failure: [],
    timeout_ms: 60000,
    capture_proof: true,
    checkpoint: false,
    skippable: false,
  }
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    return axiosErr.response?.data?.detail || 'An unexpected error occurred'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export default function ValidationWorkflowBuilderPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isNew = id === 'new'
  const { data: existingWorkflow, isLoading } = useWorkflow(isNew ? undefined : id)
  const createWorkflow = useCreateWorkflow()
  const updateWorkflow = useUpdateWorkflow(id || '')

  const [name, setName] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [description, setDescription] = useState('')
  const [graph, setGraph] = useState<WorkflowGraph>(DEFAULT_GRAPH)
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'step' | 'settings'>('settings')
  const [error, setError] = useState<string | null>(null)
  const [showRunPanel, setShowRunPanel] = useState(false)
  const [lastRunId, setLastRunId] = useState<string | null>(null)

  useEffect(() => {
    if (existingWorkflow) {
      setName(existingWorkflow.name)
      setVersion(existingWorkflow.version)
      setDescription(existingWorkflow.description || '')
      setGraph(existingWorkflow.workflow_graph as WorkflowGraph)
    }
  }, [existingWorkflow])

  const issues = useMemo(() => validateWorkflowGraph(graph), [graph])
  const hasErrors = issues.some((i) => i.type === 'error')

  const addStep = (type: WorkflowStepType) => {
    const newStep = makeEmptyStep(type, graph.steps.length)
    setGraph((g) => ({ ...g, steps: [...g.steps, newStep] }))
    if (!graph.entry_step) setGraph((g) => ({ ...g, entry_step: newStep.id }))
    setSelectedStepId(newStep.id)
    setActiveTab('step')
  }

  const loadTemplate = (templateName: string) => {
    const templateGraph = loadWorkflowTemplate(templateName)
    if (templateGraph) {
      setGraph(templateGraph)
      setSelectedStepId(null)
      setActiveTab('settings')
    }
  }

  const updateStep = (updatedStep: WorkflowStep) => {
    setGraph((g) => ({
      ...g,
      steps: g.steps.map((s) => (s.id === updatedStep.id ? updatedStep : s)),
    }))
  }

  const removeStep = (stepId: string) => {
    setGraph((g) => ({
      ...g,
      steps: g.steps.filter((s) => s.id !== stepId),
      entry_step: g.entry_step === stepId ? '' : g.entry_step,
    }))
    if (selectedStepId === stepId) setSelectedStepId(null)
  }

  const moveStep = (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= graph.steps.length) return
    const next = [...graph.steps]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    setGraph((g) => ({ ...g, steps: next }))
  }

  const handleSave = async () => {
    setError(null)
    if (hasErrors) return
    try {
      const payload = { name, version, description, workflow_graph: graph }
      if (isNew) {
        const created = await createWorkflow.mutateAsync(payload)
        navigate(`/validation-workflows/${created.id}/builder`, { replace: true })
      } else {
        await updateWorkflow.mutateAsync({ workflow_graph: graph, description })
      }
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const selectedStep = graph.steps.find((s) => s.id === selectedStepId) || null

  if (isLoading) return <LoadingSpinner fullscreen />

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/validation-workflows')} className="btn-ghost p-2">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="page-title text-lg">{isNew ? 'New Workflow' : name}</h1>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {graph.steps.length} step{graph.steps.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowRunPanel((s) => !s)} className="btn-secondary flex items-center gap-2">
            <Play className="w-4 h-4" /> Run
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={createWorkflow.isPending || updateWorkflow.isPending || hasErrors}
            className="btn-primary flex items-center gap-2"
          >
            {(createWorkflow.isPending || updateWorkflow.isPending) && <Loader2 className="w-4 h-4 animate-spin" />}
            <Save className="w-4 h-4" /> Save
          </button>
        </div>
      </header>

      {error && <div className="mx-6 mt-4 card border-l-4 border-l-red-500 p-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      <div className="mx-6 mt-4">
        <ValidationIssuesPanel issues={issues} />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-0 overflow-hidden">
        <div className="lg:col-span-2 border-r border-surface-200 dark:border-surface-700 overflow-y-auto">
          <StepPalette onAddStep={addStep} onLoadTemplate={loadTemplate} />
        </div>

        <div className="lg:col-span-5 border-r border-surface-200 dark:border-surface-700 overflow-y-auto">
          <StepList
            steps={graph.steps}
            selectedId={selectedStepId}
            entryStep={graph.entry_step}
            onSelect={(id) => {
              setSelectedStepId(id)
              setActiveTab('step')
            }}
            onRemove={removeStep}
            onMove={moveStep}
          />
          <GraphPreview graph={graph} />
        </div>

        <div className="lg:col-span-5 overflow-y-auto">
          <div className="flex border-b border-surface-200 dark:border-surface-700">
            <button
              onClick={() => setActiveTab('settings')}
              className={`flex-1 py-2 text-sm font-medium ${activeTab === 'settings' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-surface-500'}`}
            >
              Workflow
            </button>
            <button
              onClick={() => setActiveTab('step')}
              disabled={!selectedStep}
              className={`flex-1 py-2 text-sm font-medium ${activeTab === 'step' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-surface-500'}`}
            >
              Step
            </button>
          </div>

          {activeTab === 'settings' ? (
            <WorkflowSettingsPanel
              name={name}
              version={version}
              description={description}
              graph={graph}
              onChangeName={setName}
              onChangeVersion={setVersion}
              onChangeDescription={setDescription}
              onChangeGraph={setGraph}
            />
          ) : (
            <StepConfigPanel step={selectedStep} graph={graph} onChangeStep={updateStep} onRemoveStep={removeStep} />
          )}

          {showRunPanel && existingWorkflow && (
            <RunWorkflowPanel
              workflow={existingWorkflow}
              onRunCreated={(run) => {
                setLastRunId(run.id)
                navigate(`/validation-workflows/${existingWorkflow.id}/runs/${run.id}`)
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/pages/ValidationWorkflowBuilderPage.tsx
git commit -m "feat(validation-workflow-builder): add builder page"
```

---

### Task 14: Add `ValidationWorkflowListPage`

**Files:**
- Create: `frontend/src/pages/ValidationWorkflowListPage.tsx`

**Interfaces:**
- Consumes: `useWorkflows`, `useToggleWorkflowActive`
- Produces: workflow list page

- [ ] **Step 1: Create the page**

```typescript
import { useNavigate } from 'react-router-dom'
import { Plus, Copy, GitBranch } from 'lucide-react'
import LoadingSpinner from '../components/LoadingSpinner'
import { useWorkflows, useCreateWorkflow } from '../hooks/useValidationWorkflows'
import api from '../services/api'
import type { ValidationWorkflow } from '../types'

export default function ValidationWorkflowListPage() {
  const navigate = useNavigate()
  const { data: workflows, isLoading } = useWorkflows()
  const createWorkflow = useCreateWorkflow()

  const handleClone = async (workflow: ValidationWorkflow) => {
    const res = await api.get(`/validation/workflows/${workflow.id}`)
    const full = res.data
    const cloned = await createWorkflow.mutateAsync({
      name: `${workflow.name} (copy)`,
      version: workflow.version,
      description: workflow.description,
      workflow_graph: full.workflow_graph,
    })
    navigate(`/validation-workflows/${cloned.id}/builder`)
  }

  if (isLoading) return <LoadingSpinner fullscreen />

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title">Workflow Builder</h1>
        <button onClick={() => navigate('/validation-workflows/new/builder')} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {workflows?.map((workflow) => (
          <div
            key={workflow.id}
            className="card card-hover p-4 cursor-pointer"
            onClick={() => navigate(`/validation-workflows/${workflow.id}/builder`)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <GitBranch className="w-5 h-5 text-primary-500" />
                <h3 className="font-semibold text-surface-900 dark:text-surface-100">{workflow.name}</h3>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full ${
                  workflow.active
                    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200'
                    : 'bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400'
                }`}
              >
                {workflow.active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="text-sm text-surface-500 dark:text-surface-400 mt-2 line-clamp-2">{workflow.description || 'No description'}</p>
            <div className="flex items-center justify-between mt-4">
              <span className="text-xs text-surface-400">v{workflow.version}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  handleClone(workflow)
                }}
                className="btn-ghost text-xs flex items-center gap-1"
              >
                <Copy className="w-3 h-3" /> Clone
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/pages/ValidationWorkflowListPage.tsx
git commit -m "feat(validation-workflow-builder): add workflow list page"
```

---

### Task 15: Add `ValidationWorkflowRunsPage` and `WorkflowRunDetail`

**Files:**
- Create: `frontend/src/pages/ValidationWorkflowRunsPage.tsx`
- Create: `frontend/src/components/validation-workflow-builder/WorkflowRunDetail.tsx`

**Interfaces:**
- Consumes: `useWorkflow`, `useValidationRuns`, `useValidationRun`, `useStepExecutions`, `useProofs`, `useTransitions`
- Produces: run history and detail views

- [ ] **Step 1: Create `WorkflowRunDetail.tsx`**

```typescript
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
```

- [ ] **Step 2: Create `ValidationWorkflowRunsPage.tsx`**

```typescript
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useWorkflow, useValidationRuns } from '../hooks/useValidationWorkflows'
import { WorkflowRunDetail } from '../components/validation-workflow-builder/WorkflowRunDetail'
import LoadingSpinner from '../components/LoadingSpinner'

export default function ValidationWorkflowRunsPage() {
  const { id, runId } = useParams<{ id: string; runId: string }>()
  const navigate = useNavigate()
  const { data: workflow } = useWorkflow(id)
  const { data: runs } = useValidationRuns(id)

  if (!workflow) return <LoadingSpinner fullscreen />

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/validation-workflows')} className="btn-ghost p-2">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <h1 className="page-title">Runs: {workflow.name}</h1>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        <div className="lg:col-span-1 overflow-y-auto border-r border-surface-200 dark:border-surface-700 pr-4">
          <h2 className="section-title mb-3">History</h2>
          <ul className="space-y-2">
            {runs?.map((run) => (
              <li
                key={run.id}
                onClick={() => navigate(`/validation-workflows/${id}/runs/${run.id}`)}
                className={`card p-3 cursor-pointer text-sm ${runId === run.id ? 'border-primary-400' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{run.trigger_event}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 dark:bg-surface-800">{run.status}</span>
                </div>
                <p className="text-xs text-surface-500 mt-1">{run.created_at}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="lg:col-span-2 overflow-y-auto">
          {runId ? <WorkflowRunDetail runId={runId} /> : <p className="text-surface-500">Select a run to view details.</p>}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/components/validation-workflow-builder/WorkflowRunDetail.tsx frontend/src/pages/ValidationWorkflowRunsPage.tsx
git commit -m "feat(validation-workflow-builder): add runs history and detail"
```

---

### Task 16: Wire routes and navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Consumes: new page components
- Produces: lazy-loaded routes + sidebar nav item

- [ ] **Step 1: Add lazy imports and routes in `App.tsx`**

Add near the other lazy imports:

```typescript
const ValidationWorkflowListPage = lazy(() => import('./pages/ValidationWorkflowListPage').then(m => ({ default: m.default })))
const ValidationWorkflowBuilderPage = lazy(() => import('./pages/ValidationWorkflowBuilderPage').then(m => ({ default: m.default })))
const ValidationWorkflowRunsPage = lazy(() => import('./pages/ValidationWorkflowRunsPage').then(m => ({ default: m.default })))
```

Add inside the operator-protected routes (near Methodology Designer):

```typescript
<Route path="/validation-workflows" element={<Suspense fallback={<LoadingSpinner />}><ValidationWorkflowListPage /></Suspense>} />
<Route path="/validation-workflows/:id/builder" element={<Suspense fallback={<LoadingSpinner />}><ValidationWorkflowBuilderPage /></Suspense>} />
<Route path="/validation-workflows/:id/runs/:runId?" element={<Suspense fallback={<LoadingSpinner />}><ValidationWorkflowRunsPage /></Suspense>} />
```

- [ ] **Step 2: Add sidebar item in `Layout.tsx`**

In the Core nav group, add after Methodology Designer:

```typescript
{
  name: 'Workflow Builder',
  path: '/validation-workflows',
  icon: GitBranch,
  requiredRole: 'operator',
}
```

Import `GitBranch` from `lucide-react` if not already imported.

- [ ] **Step 3: Verify**

Run:
```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
npm run lint -- --no-error-on-unmatched-pattern src/App.tsx src/components/Layout.tsx
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat(validation-workflow-builder): wire routes and navigation"
```

---

### Task 17: Add frontend tests

**Files:**
- Create: `frontend/src/test/ValidationWorkflowBuilderPage.test.tsx`

**Interfaces:**
- Consumes: builder page, React Query test wrapper
- Produces: passing tests

- [ ] **Step 1: Create the test file**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ValidationWorkflowBuilderPage from '../pages/ValidationWorkflowBuilderPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: { id: 'wf-1' } })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

function renderPage(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/validation-workflows/:id/builder" element={<ValidationWorkflowBuilderPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ValidationWorkflowBuilderPage', () => {
  it('renders the new workflow builder', () => {
    renderPage('/validation-workflows/new/builder')
    expect(screen.getByText('New Workflow')).toBeInTheDocument()
    expect(screen.getByText('Step Types')).toBeInTheDocument()
  })

  it('adds a step when a palette item is clicked', () => {
    renderPage('/validation-workflows/new/builder')
    fireEvent.click(screen.getByText('AI Evaluation'))
    expect(screen.getByText('ai_evaluation_1')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/lukeouko/carbonverify/frontend
npm run test -- src/test/ValidationWorkflowBuilderPage.test.tsx
```

Expected: tests pass.

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add frontend/src/test/ValidationWorkflowBuilderPage.test.tsx
git commit -m "test(validation-workflow-builder): add builder page tests"
```

---

### Task 18: Update documentation and changelog

**Files:**
- Modify: `docs/WORKFLOW_VALIDATION_ENGINE.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add UI builder section to `docs/WORKFLOW_VALIDATION_ENGINE.md`**

Append before "Testing":

```markdown
## UI Builder

The Workflow Builder (`/validation-workflows`) provides a visual, form-based interface for creating and editing validation workflows without writing JSON.

### Features

- **Step palette** — add any of the 11 supported step types.
- **Templates** — start from pre-built workflows such as "Document quality gate" or "HTTP health check + notify".
- **Graph preview** — live SVG diagram of nodes and edges.
- **Per-step configuration** — type-specific forms for every step config schema.
- **Client-side validation** — unique step IDs, valid next-step references, required fields, and numeric bounds.
- **Test runs** — trigger a run directly from the builder and navigate to run details.
- **Run history** — view status, step executions, proofs, and transition audit chain.

### Navigation

- `/validation-workflows` — list and clone workflows
- `/validation-workflows/new` — create a workflow from scratch or template
- `/validation-workflows/:id/builder` — edit workflow graph
- `/validation-workflows/:id/runs/:runId?` — run history and detail
```

- [ ] **Step 2: Update `CHANGELOG.md`**

Add under `[Unreleased] > Added`:

```markdown
- **Validation Workflow Builder** — Visual UI for creating and editing JSON-defined validation workflows. Includes step palette, live graph preview, per-step config forms for all 11 step types, templates, client-side graph validation, test-run trigger, and run history/proof viewer. Routes: `/validation-workflows`, `/validation-workflows/:id/builder`, `/validation-workflows/:id/runs/:runId?`.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/lukeouko/carbonverify
git add docs/WORKFLOW_VALIDATION_ENGINE.md CHANGELOG.md
git commit -m "docs: document validation workflow builder"
```

---

### Task 19: Final verification

**Files:**
- All frontend files

- [ ] **Step 1: Run full frontend checks**

```bash
cd /Users/lukeouko/carbonverify/frontend
npx tsc --noEmit
npm run lint
npm run test
npm run build
```

Expected:
- `tsc` exits 0.
- `lint` introduces no new errors (existing warnings are okay).
- `test` passes.
- `build` succeeds.

- [ ] **Step 2: Run backend regression tests**

```bash
cd /Users/lukeouko/carbonverify/backend
source .venv/bin/activate
pytest tests/test_validation_engine.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit any fixes and push**

```bash
cd /Users/lukeouko/carbonverify
git push origin main
```

---

## Self-Review Checklist

| Spec Requirement | Task |
|------------------|------|
| Three-pane builder layout | Task 13 |
| Step palette with 11 types | Task 6 |
| Templates | Task 3, 13 |
| Per-step config forms | Task 10 |
| Workflow settings | Task 9 |
| Graph preview | Task 8 |
| Client-side validation | Task 12, 13 |
| Test runs | Task 11, 13 |
| Run history + detail | Task 15 |
| Routes + nav | Task 16 |
| Tests | Task 17 |
| Docs + changelog | Task 18 |

No placeholders remain. All file paths are exact. Type and function names are consistent across tasks.
