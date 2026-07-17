# Workflow Validation Engine

CarbonVerify's **Workflow Validation Engine** is an enterprise-grade autonomous QA system. It lets operators and engineers define verification workflows as JSON graphs, execute them against projects and data sources, and produce an auditable chain of cryptographic proofs.

Workflows are stored in `validation_workflows.workflow_graph` (PostgreSQL JSONB) and are validated by Pydantic schemas before they are persisted. Each run progresses through a deterministic state machine, captures per-step proof artifacts, and can anchor a Merkle root to the Radix ledger.

---

## State machine

```
PENDING → QUEUED → RUNNING → STEP_VALIDATING → PROOF_GENERATING
                                    ↓
                        REMEDIATION_CHECKING
                                    ↓
                    COMPLETED / FAILED → ARCHIVED
```

Every state transition is recorded in `validation_run_transitions` with a SHA-256 transition hash that chains to the previous transition hash for integrity.

---

## Step types

A workflow graph contains one or more steps. The engine supports the following step types:

| Step type | Purpose |
|-----------|---------|
| `http_request` | Call an HTTP endpoint and capture request/response |
| `database_query` | Run a read-only `SELECT` query and snapshot the result |
| `service_call` | Call a registered internal service method |
| `external_api` | Call an external provider (`kimi`, `radix`, `whatsapp`) |
| `notification` | Send email, SMS, WhatsApp, Slack, webhook, or in-app notification |
| `dom_capture` | Capture a web page's DOM/screenshot with Playwright |
| `decision_gate` | Evaluate a condition expression and optionally require human approval |
| `ai_evaluation` | Use an LLM to evaluate workflow data against a configurable threshold |
| `wait` | Pause execution for a fixed duration or polling condition |
| `parallel` | Execute multiple branches concurrently |
| `subflow` | Invoke another validation workflow as a nested subflow |

---

## AI-led evaluation step

The `ai_evaluation` step type lets a workflow call the Kimi API to evaluate arbitrary workflow context. It is useful for tasks such as:

- Checking whether uploaded documentation is complete and consistent
- Scoring the quality of a calculation explanation
- Verifying that a methodology draft meets registry-aligned criteria
- Flagging risky data before it reaches a human reviewer

### Configuration schema

```json
{
  "prompt": "Evaluate whether the project documentation explains the baseline scenario clearly.",
  "input_data": {
    "document_text": "...",
    "methodology": "VM0050"
  },
  "expected_output_schema": {
    "score": "float 0.0-1.0",
    "passed": "bool",
    "reasoning": "string",
    "recommendation": "string"
  },
  "pass_threshold": 0.7,
  "fail_on_error": true,
  "temperature": 0.2,
  "max_tokens": 1536
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `prompt` | string | Yes | — | The evaluation prompt sent to the LLM |
| `input_data` | object | No | `{}` | Structured data from the workflow context to include in the prompt |
| `expected_output_schema` | object | No | `null` | Descriptive JSON schema for the expected LLM response |
| `pass_threshold` | float | No | `0.7` | Minimum score for the step to be considered successful (0.0–1.0) |
| `fail_on_error` | bool | No | `true` | Whether parse errors or below-threshold scores should fail the step |
| `temperature` | float | No | `0.2` | LLM sampling temperature (0.0–2.0) |
| `max_tokens` | int | No | `1536` | Maximum tokens for the LLM response (100–8192) |

The executor merges `input_data` with the workflow's global `variables` and run metadata (`run_id`, `trigger_event`) before sending the prompt.

### Expected LLM response

The LLM must return JSON with the following keys:

```json
{
  "score": 0.85,
  "passed": true,
  "reasoning": "The baseline is described with sufficient detail and references IPCC factors.",
  "recommendation": "Approve the documentation."
}
```

- `score` — numeric score from `0.0` to `1.0`
- `passed` — boolean; if omitted, the executor derives it from `score >= pass_threshold`
- `reasoning` — human-readable explanation
- `recommendation` — suggested next action

The executor tolerates markdown JSON fences (for example, ` ```json ... ``` `) and returns structured output.

### Step result

On success the executor returns:

```json
{
  "score": 0.85,
  "passed": true,
  "reasoning": "...",
  "recommendation": "...",
  "raw_response": "...",
  "latency_ms": 420,
  "pass_threshold": 0.7
}
```

If `passed` is `false` and `fail_on_error` is `true`, the executor raises a `RuntimeError` so the orchestrator can trigger remediation or mark the run as failed.

If `fail_on_error` is `false`, the executor returns a failure result with `score: 0.0`, `passed: false`, and an error/reasoning field instead of raising.

### Proof artifacts

Each `ai_evaluation` step produces two proof records:

- `ai_evaluation_request` — the prompt, input context, and configuration
- `ai_evaluation_response` — the raw LLM response, parsed score, and reasoning

Both are hashed with SHA-256 and included in the run's Merkle tree.

---

## Example workflow graph

```json
{
  "version": "1.0",
  "description": "Validate uploaded project documentation with an AI evaluation",
  "entry_step": "check_docs",
  "steps": [
    {
      "id": "check_docs",
      "name": "AI documentation quality check",
      "type": "ai_evaluation",
      "config": {
        "prompt": "Rate the completeness and clarity of the project documentation on a scale of 0.0 to 1.0. Return score, passed, reasoning, and recommendation.",
        "input_data": {
          "document_summary": "${document_summary}"
        },
        "pass_threshold": 0.75,
        "fail_on_error": true,
        "temperature": 0.2,
        "max_tokens": 1024
      },
      "next_on_success": ["end"],
      "next_on_failure": ["fail"]
    }
  ],
  "variables": {
    "document_summary": "Project baseline and monitoring plan"
  }
}
```

Create the workflow through the API:

```bash
curl -X POST "$API/validation/workflows" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "documentation-quality-check",
    "version": "1.0.0",
    "description": "AI-led documentation quality gate",
    "workflow_graph": { ... }
  }'
```

Trigger a run:

```bash
curl -X POST "$API/validation/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "<workflow-id>",
    "project_id": "<project-id>",
    "trigger_event": "document_uploaded",
    "input_data": { "document_summary": "..." }
  }'
```

---

## API endpoints

All endpoints live under `/validation/*`:

- `POST /validation/workflows` — create a workflow
- `GET /validation/workflows` — list workflows
- `GET /validation/workflows/{id}` — get a workflow
- `PATCH /validation/workflows/{id}` — update a workflow
- `DELETE /validation/workflows/{id}` — deactivate/delete a workflow
- `POST /validation/runs` — trigger a validation run
- `GET /validation/runs` — list runs
- `GET /validation/runs/{id}` — get run status and output
- `GET /validation/runs/{id}/steps` — list step executions
- `GET /validation/runs/{id}/proofs` — list proof artifacts
- `GET /validation/runs/{id}/certificate` — download proof certificate
- `POST /validation/runs/{id}/human-decision` — submit a human decision for a decision gate
- `GET /validation/escalations` — list human escalations
- `POST /validation/escalations/{id}/acknowledge` — acknowledge an escalation
- `POST /validation/escalations/{id}/resolve` — resolve an escalation
- `GET /validation/synthetic-actors` — list synthetic actors
- `POST /validation/synthetic-actors` — create a synthetic actor

---

## Configuration

The `ai_evaluation` step uses the same Kimi API configuration as the rest of the platform:

```bash
KIMI_API_KEY=your_key_here
```

If `KIMI_API_KEY` is not set, the Kimi client returns a fallback response. In production, a real key is required for meaningful evaluations.

---

## Testing

Run the validation engine tests:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_validation_engine.py -v
```

AI evaluation tests cover:

- Passing evaluation above the threshold
- Failing evaluation below the threshold
- Malformed JSON responses when `fail_on_error` is false
- Pydantic schema validation for `AiEvaluationConfig`
- Registry lookup for `ai_evaluation` executors

---

## Integration with the rest of CarbonVerify

- Workflows can reference projects via `project_id` and receive run input via `input_data`.
- Proof certificates can be attached to VVB submissions or corporate due-diligence packages.
- Decision gates and AI evaluation steps can route to human escalation when confidence is low.
- Synthetic actors can inject traceable markers into `http_request` and `dom_capture` steps.
