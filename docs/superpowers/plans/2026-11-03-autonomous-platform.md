# CarbonVerify Autonomous Platform — Implementation Plan

Date: 2026-11-03. Goal: 90% no-touch / 9% queued approval / 1% escalation across all MRV workflows.

## Codebase reality (from exploration)

Already exists and is reused, not rebuilt:
- `backend/app/agents/` — 7 agents (base.py with confidence tiers ≥0.95 auto / ≥0.85 review / <0.85 escalate), AGENT_REGISTRY.
- `backend/app/orchestrator/` — KimiClawOrchestrator, EventLogger, Redis pub/sub, HumanReviewQueue integration.
- `backend/app/validation_engine/` — mature: state machine, 17 executors, Merkle proofs + Radix anchor, RemediationEngine (retry/rollback/skip/patch/circuit-break/escalate), SyntheticActorFactory, HumanEscalation L1–L4.
- `backend/app/api/orchestrator.py` — trigger/state/events/agent-runs/review-queue endpoints.
- Frontend `pages/command/` — CommandLayout + InboxPage (approval queue w/ approve/escalate), AgentPerformancePage, QualityMetricsPage, VVBPipelinePage, ProjectsGridPage, SettingsPage; `useReviewQueue` + WS notifications.
- Celery + beat (LeaderElectionScheduler), `tasks/` conventions, circuits in `core/circuit_breaker.py`, Kimi client in `services/kimi_api.py`.
- Project lifecycle enum: onboarding → data_collection → calculation → review → submitted → verified → monitoring.

## Gaps to close

1. Auto-advance is a stub (publishes event, never advances). No Celery driver moves lifecycles forward. Human-review items have no 24h SLA auto-approve. Agents never call Kimi; IngestionAgent is simulated. `learning_feedback` recorded but never consumed. No immutable decision audit record / `GET /api/v1/audit/{decision_id}`.
2. RemediationEngine exists only inside validation_engine; needs a shared service covering form errors, API timeouts/rate limits, DB deadlocks, calc anomalies, data gaps, VVB clarifications — with before/after state hashes and 3-attempt escalation.
3. Command Center exists but needs: escalation inbox with P0 (WhatsApp+SMS ≤60s) / P1 (email+push ≤2h) / P2 (daily digest), and a system health dashboard (confidence scores, agent performance, throughput).
4. Validation engine needs 15-min synthetic E2E journeys (developer, field enumerator offline→sync, calc anomaly recovery), continuous health score, deploy-blocking gate.
5. No knowledge base / vector search / learning loop.

## Key design decisions

- **Embeddings without new infra**: `embedding` column (JSONB array of floats) + cosine similarity computed in Python over fetched rows. Works on SQLite (tests) and PG (prod). No pgvector image change. Embedding provider: pluggable, default deterministic local hashing embedding so tests don't need an API key; Kimi/OpenAI-compatible endpoint used when configured.
- **Decision audit**: new `agent_decisions` table — every agent decision (auto/queued/escalated) + human overrides stored with input hash, reasoning, confidence, action taken, merkle-chained hash (sha256 of prev_hash + payload) for tamper evidence. `GET /api/v1/audit/{decision_id}` reads it; id also cross-stamped into HumanReviewQueue items and AgentRun.
- **Auto-advance safety**: orchestrator auto-advance consumes its own `auto_advance_ready` events via Celery task; per-project token budget + max transitions per run + visited-state set prevents loops; stops when next state's agents return <0.95.
- **Celery driver**: `lifecycle_scan` every 5 min finds projects whose current-state agent results meet advance criteria and triggers transitions; `human_review_sla_sweep` approves stale (≥24h) priority-3 review items automatically with audit record.
- **Kimi tool-calling**: extend `KimiAPIClient` with `chat_with_tools(messages, tools)` (OpenAI-compatible `tools` param); agents expose tools; graceful heuristic fallback when no API key (tests).
- **Escalations**: `escalation_events` table + `EscalationService` with channel dispatch (WhatsApp via existing `services/whatsapp/`, SMS via configured provider hook, email via `services/email.py`, in-app via existing WS/pubsub); P0 immediate, P1 2h, P2 daily digest task.
- **Deploy gate**: `scripts/pre_deploy_check.py` runs synthetic E2E + checks 7-day health score ≥90 and all success criteria; non-zero exit blocks release; CI job added.

## Execution order

1. **P1a foundation** (one agent): agent_decisions model+schema+audit API (`/api/v1/audit/{decision_id}`), orchestrator auto-advance via Celery + loop guards, lifecycle_scan beat task, 24h SLA auto-approve sweep, tests. Touch: models.py, schemas.py, api/audit.py (or new api/decisions.py), orchestrator/, tasks/, migration.
2. **P1b agents** (one agent): kimi tool-calling client, refactor 7 agents with real ingestion pipeline integration + Kimi reasoning + structured explainable reasoning output, confidence blend (heuristic × LLM self-eval). Touch: services/kimi_api.py, agents/, api/orchestrator.py minor, tests.
3. **P2 remediation** (one agent): shared RemediationEngine service + 6 rule categories + hash-logged attempts + 3-strike escalation + integration hooks into orchestrator/calculations/uploads/vvb. Touch: services/remediation.py new, hooks, tests.
4. **P3 escalations + UI** (two agents, backend then frontend): escalation service + endpoints + digest; Command Center: EscalationsPage, HealthDashboardPage, InboxPage context enrichment (reasoning + financial impact), App.tsx + CommandLayout nav. Touch: api/escalations.py, services/escalation.py, tasks/, frontend pages/hooks/types.
5. **P4 validation** (one agent): three synthetic E2E workflow definitions + 15-min beat schedule + health score computation + history + deploy gate script + CI step. Touch: validation_engine/, tasks/celery_app.py, scripts/, .github/workflows/ci.yml.
6. **P5 knowledge + learning** (one agent): MethodologyKnowledgeBase (models, ingestion, cosine search, auto-update task, Kimi-powered Q&A endpoint `/api/v1/knowledge/query`), AgentLearningLoop (consume learning_feedback, weekly retraining report task, calibration metrics endpoint). Touch: services/knowledge/ or app/knowledge/, api/knowledge.py, tasks/, tests.
7. **Verification** (me): add pytest-cov, coverage gate on new modules, full backend suite + ruff + mypy, frontend lint/tsc/vitest/build, E2E synthetic journey integration test, failure-injection suite proving >85% auto-remediation, update docs (ARCHITECTURE.md, README, CHANGELOG), commits per phase.

## Verification gates

- Backend: `cd backend && ruff check app/ tests/ && mypy app/ --ignore-missing-imports && pytest tests/ -v`
- New-code coverage: `pytest --cov=app.agents --cov=app.orchestrator --cov=app.services.remediation --cov=app.services.escalation --cov=app.knowledge --cov-report=term-missing` ≥80% on each new module group.
- Frontend: `cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build`
- Success criteria proved by: `tests/test_autonomous_e2e.py` (full journey no-touch), `tests/test_remediation_injection.py` (fault injection, assert >85% auto-resolved, zero data loss), validation health score endpoint reporting >90.
