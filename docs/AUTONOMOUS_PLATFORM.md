# CarbonVerify Autonomous Platform — Operator Runbook

How to run the platform day to day now that the autonomous agent layer (shipped 2026-11, plan: `docs/superpowers/plans/2026-11-03-autonomous-platform.md`) owns the MRV lifecycle. Every claim here is grounded in the code; module paths are relative to `backend/`.

---

## 1. What the 90/9/1 model means in practice

Every lifecycle transition is executed by one of 7 agents (`app/agents/`: ingestion, calculation, reporting, vvb_liaison, quality_control, validation, client_success). After each agent run, the orchestrator (`app/orchestrator/orchestrator.py`, `_handle_confidence_result`) routes on the result's confidence score:

| Confidence | What happens | Human effort |
|------------|--------------|--------------|
| ≥ 0.95 (auto-advance threshold; the learning loop can raise it per agent) | Lifecycle advances automatically (`advance_project`) | None — **the 90%** |
| 0.85 – 0.95 | `HumanReviewQueue` item, priority 3, 24h SLA | Approve/reject in the Inbox — **the 9%** |
| < 0.85 | Project pauses; priority-5 review item (4h SLA) **plus** an `EscalationEvent` (P0 or P1) | Immediate attention — **the 1%** |

Safety nets that keep this honest:

- **Stale approvals auto-close.** `human_review_sla_sweep` (hourly beat task) auto-approves pending priority ≤3 items older than 24h, recording an `AgentDecision` with `actor=system:sla_sweep` — the audit chain shows exactly what was auto-approved and why (`app/tasks/lifecycle_jobs.py`, `orchestrator.sla_auto_approve`).
- **Every decision is auditable.** Routing, human approvals/rejections, SLA auto-approvals, and escalation ack/resolve are appended to the merkle-chained `agent_decisions` table (`app/orchestrator/audit_chain.py`). You cannot edit history without detection.
- **Nothing silently heals.** The shared `RemediationEngine` (`app/remediation/`) retries routine failures (API timeouts, rate limits, calculation anomalies) with hash-logged before/after state; after 3 strikes it escalates with the full failure chain in the `context_package`.

## 2. The daily morning round (~15 minutes)

All pages are in the **Command Center** (`/command-center/*`, operator role or above).

1. **Health Dashboard** (`/command-center/health`) — start here.
   - Composite system score from `GET /api/v1/escalations/health/score`: agent confidence (30%), open escalations weighted P0=25/P1=10/P2=2 points off 100 (30%), review queue depth −5 per item (20%), remediation resolution rate (10%), validation run health (10%).
   - Below 90: find the weakest component in the breakdown before doing anything else.
2. **Validation health** — same page or `GET /api/v1/validation/health`.
   - Score = journey success 60% + remediation resolution 20% + escalation backlog 20%, snapshotted every 15 minutes.
   - Watch `consecutive_below_threshold`: **7 consecutive UTC days with a daily worst score below 90 blocks deployment** (see §6). One failed journey in the last 24h also fails the deploy gate.
3. **Escalations Inbox** (`/command-center/escalations`) — work P0s first.
   - P0 (severity ≥0.9): acknowledged in realtime; if no channel delivery succeeded, `dispatch-p0-escalations` (every minute) keeps re-sending.
   - Acknowledge, then resolve with notes — resolution notes are audit-logged as a human decision.
4. **Inbox** (`/command-center/inbox`) — the human approval queue.
   - Each item shows the agent's reasoning, confidence, and evidence from the decision audit. Approve to fire the next lifecycle step, reject to escalate, or assign to a colleague.
   - Anything here older than 24h (priority ≤3) will be auto-approved by the hourly sweep — review before it is.
5. **Agent Performance** (`/command-center/agents`) — check override rates. An agent with a rising override rate will have its auto-advance threshold raised by the learning loop; persistent overrides mean the agent's inputs or prompt need attention.
6. **Weekly**: read the retraining report (`GET /api/v1/learning/report/weekly`, generated weekly by the `generate-weekly-learning-report` beat task) — override-ranked agents with suggested threshold changes.

## 3. Escalation priorities and channel setup

`EscalationService.raise_escalation` derives priority from the 0–1 severity score (`app/escalations/service.py`):

| Priority | Severity | SLA / cadence | Channels attempted |
|----------|----------|---------------|--------------------|
| P0 | ≥ 0.9 | Realtime; redispatched every 60s until one channel succeeds | WhatsApp, SMS, email, in-app push |
| P1 | ≥ 0.7 | 2h (`send-p1-escalations`, every 30 min) | Email, in-app push |
| P2 | < 0.7 | Daily digest email | Digest only |

**All adapters are no-op-safe**: without credentials they log and record `configured: false` on the event's `channels_sent` map — the Escalations page shows per-channel delivery status. Nothing raises if a channel fails.

To enable channels, set in `.env` (see `.env.example`):

| Channel | Variables |
|---------|-----------|
| Email | `ESCALATION_NOTIFY_EMAIL` (comma-separated inboxes) + existing email config (`EMAIL_PROVIDER`, `AWS_SES_FROM_EMAIL` or `SMTP_*`) |
| WhatsApp | `ESCALATION_NOTIFY_WHATSAPP` (E.164 operator number) + `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` (Meta WhatsApp Business API) |
| SMS | `ESCALATION_NOTIFY_SMS` (E.164) + `ESCALATION_SMS_WEBHOOK_URL` (provider-agnostic HTTP hook receiving `{"to", "message"}`) |
| In-app | None — always on (pub/sub → `/ws/notifications`) |

P2s never interrupt: they aggregate into `daily-escalation-digest` (daily beat task) summarizing open P0/P1/P2 and the last 24h of P0/P1 raises.

## 4. Ingesting methodology documents into the knowledge base

`MethodologyKnowledgeBase` (`app/knowledge/`) chunks documents (500-token windows, 50-token overlap), embeds them, and serves cosine-similarity search + RAG answers cited by methodology ID. Documents are **ingested via the API only** — nothing is scraped (`check-methodology-updates` is a stub-safe daily no-op check).

```bash
# Ingest (operator role; idempotent per registry + methodology_id + version —
# re-ingesting the same triple replaces the document and its chunks)
curl -X POST "$API/api/v1/knowledge/documents" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "registry": "gold_standard",
    "methodology_id": "TPDDTEC v4",
    "title": "Technologies and Practices to Disseminate Energy Efficient Cookstoves",
    "content": "<full methodology text>",
    "version": "4.0",
    "source_url": "https://globalgoals.goldstandard.org/..."
  }'

# RAG question (viewer role; degrades to verbatim passages flagged "unreviewed"
# when KIMI_API_KEY is unset)
curl -X POST "$API/api/v1/knowledge/query" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question": "What sampling approach does TPDDTEC require for kitchen performance tests?"}'
```

Embeddings: by default a deterministic offline hashing embedder is used (no external calls). For production retrieval quality, point `KNOWLEDGE_EMBEDDER_URL` / `KNOWLEDGE_EMBEDDER_MODEL` / `KNOWLEDGE_EMBEDDER_API_KEY` at any OpenAI-compatible `/embeddings` endpoint. `KIMI_API_KEY` powers the RAG synthesis step.

## 5. Reading the health score

Two scores, different jobs:

- **System health** (`GET /api/v1/escalations/health/score`, weights in §2) — "how is operations doing right now". Drops fast when P0s are open or the review queue backs up. Must be ≥90 to pass the deploy gate.
- **Validation health** (`GET /api/v1/validation/health`) — "is the platform correctly validating itself". Snapshots every 15 minutes; the daily score is the **worst (minimum) snapshot of that UTC day**, and `consecutive_below_threshold` counts consecutive days below 90 (a healthy snapshot later the same day does not reset a bad day). Think of the streak as a burn-down timer: at 7 the deploy gate blocks, so a streak ≥3 deserves same-day investigation. Journey stats (completed/failed per journey, last 24h) are included in the response.

Both feed the Health Dashboard (`/command-center/health`); neither requires admin.

## 6. Deploy blocks

The pre-deploy gate is `backend/scripts/pre_deploy_check.py`. It fails (exit 1, reasons printed) when any of:

1. `GET /api/v1/escalations/health/score` < 90 (or unreachable — health endpoints need an operator/admin bearer token),
2. `GET /api/v1/validation/health` shows `consecutive_below_threshold` ≥ 7,
3. any synthetic journey has a failed run or no completed run in the last 24 hours,
4. (with `--with-tests`) any acceptance test fails: `tests/test_autonomous_e2e.py`, `tests/test_remediation_injection.py`, `tests/test_operator_scale.py`.

```bash
cd backend
python scripts/pre_deploy_check.py --base-url https://api.carbonverify.io --token "$OPERATOR_JWT"
python scripts/pre_deploy_check.py --with-tests      # acceptance suite as the gate
python scripts/pre_deploy_check.py --offline-selftest  # sanity-check the checker (also run in CI)
```

Defaults come from `DEPLOY_CHECK_BASE_URL` / `DEPLOY_CHECK_TOKEN`. CI runs the self-test on every push ("Deploy-gate self-test" step) and the acceptance suite as the "Success criteria" job.

## 7. Troubleshooting

**Where logs live**

- Local hybrid stack: `scripts/status-local.sh`; per-process logs in `.local-logs/` (backend, celery worker, celery beat, frontend).
- Docker Compose: `docker-compose logs -f app celery-worker celery-beat`.
- Kubernetes: `kubectl logs -f deployment/prod-carbonverify-celery-worker -n carbonverify` (see `infrastructure/docs/DEPLOYMENT.md`).
- Key log events: `orchestrator_advance_start`, `orchestrator_human_review`, `orchestrator_escalation`, `escalation_channel_attempt`, `agent_decision_recorded`, `validation_health_snapshot`, `remediation_attempt_*`, `synthetic_journey_queued`.

**A project seems stuck**

1. Check its state and agent runs: `GET /orchestrator/projects/{id}/state` and `GET /orchestrator/projects/{id}/agent-runs`.
2. If the last run's confidence was 0.85–0.95, it is waiting in the Inbox — approve/reject there (`POST /orchestrator/review-queue/{item_id}/resolve` with `{"decision": "approve"|"reject"|"escalate"}`).
3. If confidence was <0.85, an escalation exists — resolve the escalation (the project resumes via the next lifecycle scan once the underlying issue is fixed).
4. To force progress: `POST /orchestrator/projects/{id}/trigger` with `{"trigger": "<data_complete|validation_passed|calculation_complete|report_approved|registry_approved|monitoring_period_complete>"}` (operator role), or re-run one agent directly: `POST /orchestrator/projects/{id}/agents/{agent_type}/run`.
5. Note `lifecycle-scan` only considers projects created/updated in the last 7 days and driveable states (onboarding → submitted); `verified`/`monitoring` are steady states advanced by external actors (registry, VVB).

**A beat task looks stuck**

- Confirm beat holds the leader lock and is running (`docker-compose logs celery-beat` / kubectl). `LeaderElectionScheduler` elects exactly one beat via Redis — if the lock holder crashed, it re-elects within one scheduler tick.
- `run-synthetic-validation` skips a journey while its previous run is in flight (`synthetic_journey_skipped_inflight` in logs) — long-running validation runs can starve snapshots; check `GET /validation/runs` for stuck RUNNING runs.

**Remediation keeps failing**

- `GET /api/v1/remediation/stats` and `GET /api/v1/remediation/attempts` show before/after state hashes per attempt. After 3 failed rounds the engine stops and escalates — treat the escalation's `context_package.failure_chain` as the diagnosis.
- A failed attempt older than 1 hour is automatically re-run by `remediation-sweep` (max 50 targets/run) with a fresh attempt budget.

**Verifying the audit chain**

```bash
# Full-chain integrity check (viewer role)
curl -X POST "$API/api/v1/audit/verify-chain" -H "Authorization: Bearer $TOKEN"
# → {"valid": true, "checked": <n>, "first_broken_id": null}

# Inspect one decision
curl "$API/api/v1/audit/{decision_id}" -H "Authorization: Bearer $TOKEN"
# List recent decisions (filters: project_id, agent_type, action)
curl "$API/api/v1/audit/decisions?limit=50" -H "Authorization: Bearer $TOKEN"
```

`verify_chain` recomputes every record's SHA-256 (which covers the record's fields **plus the previous record's hash**) in `created_at` order; any edit, reorder, or fork is reported with the first broken `decision_id`. Appends are serialized with `SELECT ... FOR UPDATE` on the chain tip, so concurrent writers cannot fork the chain.

**Escalations not arriving**

- Check the event's `channels_sent` on the Escalations page — each channel records `configured`, `success`, and `detail`.
- WhatsApp needs all three of `ESCALATION_NOTIFY_WHATSAPP`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`; SMS needs both `ESCALATION_NOTIFY_SMS` and `ESCALATION_SMS_WEBHOOK_URL`; email needs `ESCALATION_NOTIFY_EMAIL` plus working SES/SMTP config. Empty = log-only, by design.
- P0 redelivery is every 60s (`dispatch-p0-escalations`); P1 retries every 30 min within the 2h SLA.

**Escalated agent keeps firing**

The learning loop is the fix, not the workaround: review `GET /api/v1/learning/overrides` and `GET /api/v1/learning/cibration` — if humans consistently override one agent's low-confidence calls, its suggested auto-advance threshold rises automatically (applied by the orchestrator on the next run) and the weekly report flags it. If humans consistently reject its high-confidence calls, act on the weekly report's "manual threshold review" flag and feed the agent better inputs (knowledge base documents are the usual lever for reasoning quality).

---

## 8. Quick reference

| Surface | Where |
|---------|-------|
| Approval queue | `/command-center/inbox` · `GET /orchestrator/review-queue` |
| Escalations | `/command-center/escalations` · `/api/v1/escalations/*` |
| System health | `/command-center/health` · `GET /api/v1/escalations/health/score` |
| Validation health | `GET /api/v1/validation/health` |
| Decision audit | `/api/v1/audit/decisions`, `/{id}`, `/verify-chain` |
| Remediation | `/api/v1/remediation/{rules,attempts,stats}` |
| Knowledge base | `/api/v1/knowledge/{documents,search,query}` |
| Learning loop | `/api/v1/learning/{calibration,overrides,report/weekly}` |
| Deploy gate | `backend/scripts/pre_deploy_check.py` |
| Beat schedule | `backend/app/tasks/celery_app.py` · `infrastructure/docs/DEPLOYMENT.md` |
