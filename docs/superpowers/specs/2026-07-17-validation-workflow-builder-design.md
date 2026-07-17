# Validation Workflow Builder — Design Spec

## Background

CarbonVerify's Workflow Validation Engine already supports JSON-defined workflow graphs with 11 step types, cryptographic proof chains, and AI-led evaluation. Today these workflows are created by hand-writing JSON and posting it to `POST /validation/workflows`. That is error-prone and inaccessible to consultants and operators who are not comfortable with JSON graph syntax.

## Goal

Build a **visual, detailed UI builder** that lets operators and consultants create, edit, clone, test, and manage validation workflows without writing JSON. The builder must expose every configurable field the backend supports, validate the graph visually, and let the user trigger a test run directly from the canvas.

## Non-Goals

- Replacing the JSON API. The JSON API remains the source of truth; the builder is a client on top of it.
- Building a general-purpose BPMN or robotic-process-automation designer. We stay focused on CarbonVerify's 11 step types.
- Adding an admin-only template marketplace in this iteration. Templates are local defaults shipped with the builder.
- Changing the validation engine backend state machine or proof system.

## Target Users

- **Carbon consultants** who design project-specific QA workflows.
- **Operators** who maintain reusable verification workflows.
- **Admins** who clone or deprecate workflows.

All users in this group already have the `operator` role (or higher), matching the existing `POST /validation/workflows` requirement.

## Design Overview

### Page/Route Model

| Route | Purpose | Auth |
|-------|---------|------|
| `/validation-workflows` | List all workflows; create new; clone; activate/deactivate | operator |
| `/validation-workflows/new` | Create a workflow from scratch or a template | operator |
| `/validation-workflows/:id/builder` | The builder itself | operator |
| `/validation-workflows/:id/runs` | Run history, status, proofs, transitions for a workflow | operator |

Navigation: add **Workflow Builder** to the Core sidebar group, immediately after **Methodology Designer**, using the `GitBranch` Lucide icon.

### Builder Layout

A fixed three-pane layout on desktop that collapses to stacked panels on smaller screens.

```
┌─────────────────┬───────────────────────────────┬────────────────────┐
│ PALETTE         │ CANVAS / GRAPH PREVIEW        │ CONFIG PANEL       │
│                 │                               │                    │
│ Step type chips │ Visual nodes + edges          │ Form for selected  │
│ + Templates     │ - entry node highlighted      │ step or global     │
│ + Run button    │ - success edges solid         │ workflow settings  │
│ + Save/Validate │ - failure edges dashed/red    │                    │
│                 │ - pan/zoom controls           │                    │
└─────────────────┴───────────────────────────────┴────────────────────┘
```

#### Phase 1: Form-first builder (MVP)

The first shipped version uses a **step list + read-only graph preview** rather than a full drag-and-drop canvas. This keeps dependencies minimal and matches the existing `MethodologyDesignerPage` wizard/form patterns while still being very detailed.

- **Left pane**: step type palette and template gallery.
- **Center pane**: ordered list of steps with inline next-step chips; a live SVG-based graph preview below the list.
- **Right pane**: configuration form for the selected step, plus global workflow settings (name, version, description, SLA, variables, retry policy, circuit breaker).

#### Phase 2: Interactive node canvas (future enhancement)

Replace the SVG preview with an interactive `@xyflow/react` canvas where steps are draggable nodes and edges can be rewired by dragging handles. The left/right panes stay the same. This phase adds `reactflow` as a dependency and lazy-loads it so the initial bundle is unaffected.

### Step Configuration Forms

Each step type gets its own typed form section rendered when the step is selected. Fields map 1:1 to the backend Pydantic schemas.

| Step type | Config form fields |
|-----------|--------------------|
| `ai_evaluation` | Prompt textarea, input_data JSON editor, expected_output_schema JSON editor, pass_threshold slider (0.0–1.0), fail_on_error checkbox, temperature slider, max_tokens number |
| `http_request` | Method select, URL input, headers key/value editor, body JSON editor, timeout_ms, expected_status_codes multi-number input, capture_response checkbox |
| `database_query` | Query textarea (SELECT only), params JSON editor, expected_row_count number, snapshot_result checkbox |
| `service_call` | Service name input, method name input, args JSON editor, kwargs JSON editor, capture_io checkbox |
| `external_api` | Provider select (`kimi`, `radix`, `whatsapp`), endpoint input, method select, params JSON editor, timeout_ms |
| `notification` | Channel select (`email`, `sms`, `whatsapp`, `slack`, `webhook`, `in_app`), template_id, recipients list, subject, body, priority select |
| `dom_capture` | URL input, selector, full_page checkbox, capture_screenshot, capture_html, viewport width/height |
| `decision_gate` | Condition expression input, require_human_approval checkbox, auto_approve_threshold slider, timeout_seconds, escalation_level select |
| `wait` | Duration ms number, optional polling condition string |
| `parallel` | Branch step-id multi-select, join_strategy select (`all`/`any`/`first`/`custom`), max_concurrency number |
| `subflow` | Workflow name input, version input, input_mapping key/value editor, output_mapping key/value editor |

Common fields shown for every step:

- Step ID (slug-like, unique in workflow)
- Step name
- Description
- Enabled toggle
- Timeout ms
- Capture proof toggle
- Checkpoint toggle
- Skippable toggle
- Retry policy override (optional)
- Next on success (multi-select of step IDs or `end`)
- Next on failure (multi-select of step IDs or `fail`)

### Workflow-Level Configuration

Always visible in the right pane via a "Workflow Settings" tab:

- Name
- Version
- Description
- Entry step (dropdown of step IDs)
- SLA seconds
- Human gates required (global default)
- Global retry policy (max_retries, backoff_multiplier, initial_delay_ms, retry_on tags)
- Circuit breaker config (failure_threshold, recovery_timeout_ms, half_open_max_calls)
- Global variables (JSON key/value editor)

### Graph Validation (Client-Side)

The builder validates the graph before the user can save. Errors are shown inline and in a floating validation panel.

Rules:

1. Step IDs are unique and match `^[a-zA-Z0-9_\-]+$`.
2. Entry step is set and points to an existing step.
3. Every `next_on_success` / `next_on_failure` value is either a known step ID, `end`, or `fail`.
4. No orphaned steps (a step that is not reachable from the entry step) — shown as a warning, not a hard error.
5. No cycles that lack an exit path — warning.
6. Step config validates against the selected step type's schema (e.g., `pass_threshold` 0.0–1.0, HTTP method in allowed set).
7. Required fields are filled.

### Templates

The builder ships with a small set of reusable workflow templates shown in the left pane:

- **Document quality gate** — one `ai_evaluation` step that scores project documentation.
- **Data source completeness check** — `database_query` + `decision_gate` verifying expected row counts.
- **HTTP health check + notify** — `http_request` + `notification` on failure.
- **Full VVB review pipeline** — `http_request` (fetch documents) → `ai_evaluation` (quality) → `decision_gate` (human approval) → `notification` (outcome).

Templates are stored as static JSON in `frontend/src/lib/validationWorkflowTemplates.ts`. Users can load a template into a new workflow and then customize it.

### Synthetic Actors

The backend already supports synthetic actors at the run level (injected into step context by the orchestrator). The builder MVP does **not** add per-step synthetic-actor selection because `WorkflowStep` has no such field. Instead, a future enhancement can add a run-level synthetic-actor picker in the **Run workflow** panel that passes actor context via `input_data` or a dedicated run option when the API supports it.

### Test Runs from the Builder

A **Run workflow** button in the top toolbar opens a side panel where the user enters:

- `project_id` (optional dropdown of existing projects)
- `trigger_event` (default `manual_test`)
- `input_data` (JSON editor)

On submit, the frontend calls `POST /validation/runs` and then polls `GET /validation/runs/{run_id}` until the run reaches a terminal state. The run status, step executions, and any error message are shown inline. If the run completes, a **View proofs** link opens the run detail view (`/validation-workflows/:id/runs/:runId`).

### Run History View

`/validation-workflows/:id/runs` displays a paginated table of runs for the workflow:

- Status badge
- Trigger event
- Project (if any)
- Confidence score
- Started / completed timestamps
- Actions: view steps, view proofs, download certificate, re-run

Clicking a run opens a detail view with tabs for:

- **Overview** — status, error, merkle root, radix tx ref
- **Steps** — list of step executions with duration and status
- **Proofs** — proof type, captured at, download link
- **Transitions** — immutable audit chain

### Data Flow & State Management

- **Server state**: React Query v5 hooks in a new file `frontend/src/hooks/useValidationWorkflows.ts`.
  - `useWorkflows()`, `useWorkflow(id)`, `useCreateWorkflow()`, `useUpdateWorkflow()`, `useCloneWorkflow()`, `useToggleWorkflowActive()`.
  - `useValidationRuns(workflowId)`, `useValidationRun(runId)`, `useTriggerRun()`.
  - `useSyntheticActors()`.
- **Builder client state**: a single Zustand store or `useState` reducer (`useWorkflowBuilder`) holding the in-memory `WorkflowGraph`, selected step ID, dirty flag, and validation errors. No Zustand store is required if `useState` + prop drilling is manageable, but a small local store keeps the top-level page component clean.
- **Form state**: each step config form receives the step object and a `patchStep(id, partial)` callback. JSON fields use a small `JsonEditor` component (textarea with `JSON.parse` validation) because the project does not currently include a JSON editor dependency.

### Error Handling

- API errors surface in a top banner on the builder page using the existing `getErrorMessage(err)` pattern.
- Graph validation errors block the Save button and are listed in a sticky "N issues" panel.
- JSON parse errors in config fields show per-field red text.
- Test-run failures display the run's `error_message` and failed step ID.

### Components to Create

| Component | Path |
|-----------|------|
| `ValidationWorkflowBuilderPage` | `frontend/src/pages/ValidationWorkflowBuilderPage.tsx` |
| `ValidationWorkflowListPage` | `frontend/src/pages/ValidationWorkflowListPage.tsx` |
| `ValidationWorkflowRunsPage` | `frontend/src/pages/ValidationWorkflowRunsPage.tsx` |
| `WorkflowBuilderLayout` | `frontend/src/components/validation-workflow-builder/WorkflowBuilderLayout.tsx` |
| `StepPalette` | `frontend/src/components/validation-workflow-builder/StepPalette.tsx` |
| `StepList` | `frontend/src/components/validation-workflow-builder/StepList.tsx` |
| `GraphPreview` | `frontend/src/components/validation-workflow-builder/GraphPreview.tsx` |
| `StepConfigPanel` | `frontend/src/components/validation-workflow-builder/StepConfigPanel.tsx` |
| `WorkflowSettingsPanel` | `frontend/src/components/validation-workflow-builder/WorkflowSettingsPanel.tsx` |
| `JsonEditor` | `frontend/src/components/validation-workflow-builder/JsonEditor.tsx` |
| `KeyValueEditor` | `frontend/src/components/validation-workflow-builder/KeyValueEditor.tsx` |
| `MultiSelectChips` | `frontend/src/components/validation-workflow-builder/MultiSelectChips.tsx` |
| `ValidationIssuesPanel` | `frontend/src/components/validation-workflow-builder/ValidationIssuesPanel.tsx` |
| `RunWorkflowPanel` | `frontend/src/components/validation-workflow-builder/RunWorkflowPanel.tsx` |
| `WorkflowRunDetail` | `frontend/src/components/validation-workflow-builder/WorkflowRunDetail.tsx` |

### TypeScript Types to Add

Add to `frontend/src/types/index.ts`:

```typescript
export type WorkflowStepType =
  | 'http_request' | 'database_query' | 'service_call' | 'external_api'
  | 'notification' | 'dom_capture' | 'decision_gate' | 'ai_evaluation'
  | 'wait' | 'parallel' | 'subflow'

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
  sla_seconds?: number
  human_gates_required: boolean
  created_at: string
  updated_at: string
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

### Dependencies

Phase 1 adds no new runtime dependencies beyond existing React, React Query, Axios, Zustand, Lucide, Tailwind.

Phase 2 (interactive canvas) adds:

- `@xyflow/react` (React Flow v12) for the node canvas.
- Lazy-load the canvas component so it only affects the builder chunk.

### Testing Plan

#### Frontend unit/component tests

- Builder renders palette, step list, and config panel.
- Adding a step increases step count.
- Selecting a step shows the correct config form.
- Saving a workflow calls `PATCH /validation/workflows/:id` with the expected graph.
- Validation errors appear when two steps share the same ID.
- Triggering a test run calls `POST /validation/runs` and polls for status.

#### End-to-end manual QA

- Create a workflow from the "Document quality gate" template.
- Edit the `ai_evaluation` prompt and pass threshold.
- Add a `notification` step on failure.
- Save successfully.
- Trigger a test run with a project and verify the run reaches `completed` or `failed`.
- View proofs and certificate.

#### Backend regression

- Run `pytest tests/test_validation_engine.py -v` and full `pytest tests/` to ensure the builder does not change backend behavior.

## Future Enhancements

- Drag-and-drop node canvas (Phase 2).
- Admin template CRUD UI backed by a new `workflow_templates` table.
- Inline AI helper that drafts an `ai_evaluation` prompt from step context.
- Real-time run progress via WebSocket or SSE.
- Diff view when updating a workflow graph.

## Appendix: Example Template JSON

```json
{
  "name": "Document quality gate",
  "version": "1.0.0",
  "description": "Use AI to score project documentation and notify on failure.",
  "workflow_graph": {
    "version": "1.0",
    "description": "AI-led documentation quality gate",
    "entry_step": "evaluate_docs",
    "steps": [
      {
        "id": "evaluate_docs",
        "name": "Evaluate documentation",
        "type": "ai_evaluation",
        "config": {
          "prompt": "Rate the completeness and clarity of the project documentation on a scale of 0.0 to 1.0. Return score, passed, reasoning, and recommendation.",
          "input_data": { "document_summary": "${document_summary}" },
          "pass_threshold": 0.75,
          "fail_on_error": true,
          "temperature": 0.2,
          "max_tokens": 1024
        },
        "next_on_success": ["end"],
        "next_on_failure": ["notify_team"]
      },
      {
        "id": "notify_team",
        "name": "Notify team",
        "type": "notification",
        "config": {
          "channel": "email",
          "recipients": ["operator@carbonverify.demo"],
          "subject": "Documentation quality gate failed",
          "body": "The AI evaluation step failed. Please review the project documentation.",
          "priority": "high"
        },
        "next_on_success": ["fail"],
        "next_on_failure": ["fail"]
      }
    ],
    "variables": { "document_summary": "" }
  }
}
```
