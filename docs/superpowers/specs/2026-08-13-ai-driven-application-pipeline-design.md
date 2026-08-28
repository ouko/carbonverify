# AI-Driven Carbon Credit Application Pipeline — Design Spec

**Date:** 2026-08-13  
**Status:** Draft — pending review  
**Approach:** A — extend the existing validation workflow engine

---

## 1. Goal

Make CarbonVerify an AI-driven application intake system by default. The system should:

1. Collect carbon-credit project applications from clients (inbound self-service and discovered registry leads).
2. Ingest project documents from wherever they live (manual upload, email, cloud storage, registry portals).
3. Review documents automatically for completeness, consistency, and audit readiness.
4. Identify gaps against the chosen methodology / registry requirements.
5. Help the applicant fill those gaps via AI-generated guidance, clarifying questions, and template generation.
6. Advance the application toward audit readiness and registry submission without waiting for scarce human audit resources.

The existing CarbonVerify codebase already contains the core building blocks. This spec describes how to wire them into a single, AI-first application pipeline.

---

## 2. Assumptions

- **Primary actors:** Project developers use a public/self-service intake portal; CarbonVerify consultants use the same pipeline as an internal case-management view.
- **Automation level:** Hybrid by confidence. The system auto-advances high-confidence steps, queues human review for medium-confidence steps, and escalates low-confidence or blocked steps.
- **Scope:** Inbound application processing and audit readiness. Outbound marketing and sales outreach are out of scope.
- **Compliance:** Human approval remains mandatory before registry submission and before any legally binding representation.
- **AI provider:** Moonshot Kimi via the existing `KimiAPIClient`.

---

## 3. High-Level Architecture

The pipeline is implemented as a new top-level validation workflow template named `ai_application_pipeline`. It orchestrates existing services and adds a small number of domain-specific step executors.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Intake Sources │────▶│ Application Run  │────▶│  AI Pipeline    │
│ (portal, email, │     │ (ValidationRun   │     │ (Validation     │
│  registry, API) │     │  + Application)  │     │  Workflow)      │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
       ┌──────────────────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Intake & Classification                           │
│  - Create Application record                                │
│  - Classify project type / sector / likely methodology      │
│  - Ingest documents from all sources                        │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Document Understanding                            │
│  - Extract text / tables / GPS / dates                      │
│  - Classify documents (PDD, monitoring report, KPT, etc.)   │
│  - Virus scan, hash, S3 store                               │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Gap Analysis & Pre-Audit                          │
│  - Compare documents to methodology checklist               │
│  - AI evaluation of readiness                               │
│  - Produce gap list with severity                           │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: Gap Remediation                                   │
│  - AI drafts missing sections / clarifications              │
│  - Request additional docs from applicant                   │
│  - Generate methodology if no standard fit                  │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 5: Calculation & Report                              │
│  - Run calculations when data is sufficient                 │
│  - Generate monitoring/PDD report                           │
│  - Run quality gates                                        │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 6: Human Gate & Registry Submission                  │
│  - Consultant approves final package                        │
│  - Submit to Verra / Gold Standard / Kenya National         │
│  - Poll registry status                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. New Domain Model

### 4.1 `Application` entity

A new table that sits above `Project` during the intake phase. Once the application is approved, it promotes to a full `Project`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `applicant_email_hash` | str | Searchable hash for applicant lookup |
| `applicant_email_encrypted` | str | Encrypted applicant email |
| `organization_name` | str | Organization applying |
| `project_title` | str | Working title |
| `country` | str | Project country |
| `sector` | str | Sector (cookstoves, forestry, renewable, etc.) |
| `proposed_methodology` | str | Selected or AI-suggested methodology |
| `status` | enum | `intake`, `documents_pending`, `pre_audit`, `gaps`, `ready_for_calculation`, `ready_for_review`, `approved`, `submitted`, `rejected` |
| `confidence_score` | float | Overall pipeline confidence 0–1 |
| `converted_project_id` | UUID FK | Link after promotion |
| `validation_run_id` | UUID FK | Active `ValidationRun` driving the pipeline |
| `created_at`, `updated_at` | datetime | Audit timestamps |

### 4.2 `ApplicationDocument` entity

Tracks documents attached to an application before promotion to `Project`/`FileUpload`.

| Field | Purpose |
|-------|---------|
| `application_id` | FK |
| `source_type` | `upload`, `email`, `drive`, `dropbox`, `registry`, `api` |
| `source_url` | Original location |
| `s3_key` | Stored location |
| `document_type` | AI-classified type |
| `status` | `discovered`, `fetched`, `scanning`, `processed`, `failed` |
| `extracted_text` | Text extracted for AI review |
| `gap_findings` | JSONB of missing/wrong items found in this doc |

### 4.3 Workflow template: `ai_application_pipeline`

Stored as a `ValidationWorkflow` with `workflow_graph` JSON. The graph contains the six phases above and uses both existing step types and new step types.

---

## 5. New Step Executors

Add the following executors to `backend/app/validation_engine/executors.py`:

### 5.1 `application_intake`

Creates the `Application` record from portal/email/API payload.

**Config:** `applicant_email`, `organization_name`, `project_title`, `country`, `sector`, `proposed_methodology`.

**Output:** `application_id`, `status=intake`.

### 5.2 `document_collection`

Gathers documents from configured sources.

**Config:** `sources: [{type, connection_id, folder_id, registry_source, external_id}]`, `required_document_types`.

**Behavior:**
- Manual upload: wait for files via API.
- Email: poll IMAP/webhook for tagged emails with attachments.
- Cloud storage: OAuth connector (Google Drive, Dropbox, OneDrive) listing a folder.
- Registry: reuse `RegistryDocumentFetcher` from lead intelligence.

**Output:** `collected_documents: [{document_id, type, status, s3_key}]`.

### 5.3 `document_ai_classification`

Classifies each collected document and extracts key metadata.

**Behavior:**
- Reuse `pdf.py`, `excel_csv.py`, `image.py` pipelines.
- Call Kimi to classify into `PDD`, `monitoring_report`, `KPT_results`, `sales_receipt`, `survey_form`, `GPS_data`, `stove_inventory`, `other`.
- Extract dates, GPS bounds, monitoring period, methodology references.

**Output:** `classified_documents`, `extracted_entities`.

### 5.4 `methodology_match`

Determines whether the project fits an existing methodology or needs a custom one.

**Behavior:**
- Reuse `MethodologyGeneratorService.analyze_gap()`.
- If standard fit: output `methodology` and `required_document_types`.
- If no fit: trigger methodology generation workflow.

**Output:** `methodology`, `required_document_types`, `custom_methodology_needed`.

### 5.5 `gap_analysis`

Compares collected documents + extracted entities against the methodology checklist.

**Behavior:**
- Build a system prompt from the methodology requirements.
- Use `AiEvaluationExecutor` pattern to score readiness and produce a structured gap list.
- Gaps have severity (`critical`, `major`, `minor`) and remediation type (`missing_document`, `missing_section`, `inconsistent_data`, `clarification_needed`).

**Output:** `readiness_score`, `gaps: [{id, severity, type, description, remediation_hint}]`, `status`.

### 5.6 `gap_remediation`

Generates remediation artifacts for each gap.

**Behavior:**
- For `missing_section`: draft text using Kimi and project context.
- For `missing_document`: generate a request email/questionnaire for the applicant.
- For `inconsistent_data`: flag for human review with explanation.
- For `clarification_needed`: generate specific follow-up questions.

**Output:** `remediation_actions`, `drafts`, `outstanding_requests`.

### 5.7 `applicant_interaction`

Sends requests to the applicant and waits for responses.

**Behavior:**
- Sends email/WhatsApp/in-app notification with a secure link.
- Secure link opens a minimal portal where the applicant uploads docs or answers questions.
- Webhook/API updates the workflow when response arrives.

**Output:** `responses_received`, `documents_added`, `questions_answered`.

### 5.8 `promote_to_project`

Converts the `Application` into a full `Project` and links documents as `FileUpload`/`DataSource`.

**Behavior:**
- Reuse `LeadToProjectConverter` pattern.
- Create `Project`, `DataSource`, and `FileUpload` records.
- Trigger calculation workflow when ready.

**Output:** `project_id`.

---

## 6. Reuse of Existing Systems

| Existing system | Reuse in the pipeline |
|-----------------|----------------------|
| `validation_engine` | Orchestrates the entire pipeline, proofs, remediation, escalation |
| `KimiAPIClient` | All LLM calls for classification, gap analysis, drafting |
| Lead intelligence scrapers | Discover and pre-populate applications from registries |
| `RegistryDocumentFetcher` | Fetch documents from registry project pages |
| Upload API + ClamAV + S3 | Ingest and store applicant documents |
| Document processing pipelines | Extract text, tables, GPS, dates |
| `MethodologyGeneratorService` | Custom methodology drafting when no standard fit |
| Calculation engine | Run fNRB/emissions/leakage/uncertainty once data is ready |
| Report generator | Generate PDD/monitoring report PDFs |
| VVB liaison | Submit to registries and poll status |
| Human review queue | Consultant checkpoints and overrides |
| Audit logger | Immutable hash-chain log of all actions |

---

## 7. Confidence-Based Automation

Each step executor returns a `confidence_score` (0–1). The orchestrator uses the existing `AgentResult` thresholds:

| Confidence | Action |
|------------|--------|
| ≥ 0.95 | Auto-advance to next step |
| 0.85 – 0.94 | Continue but create a low-priority human review queue item |
| 0.70 – 0.84 | Pause and request human review before continuing |
| < 0.70 | Escalate via `HumanEscalation` with severity `high` |

The overall `Application.confidence_score` is the geometric mean of phase-level confidence scores, weighted by phase criticality.

---

## 8. Human Escalation & Consultant UI

The pipeline uses the existing `HumanEscalation` system:

- **L1 Operator:** Review flagged documents or low-confidence classifications.
- **L2 Engineer:** Resolve methodology mismatches or calculation issues.
- **L3 Architect:** Approve custom methodologies or non-standard approaches.
- **Executive:** Approve go/no-go on high-value or high-risk submissions.

A new **Applications** page in the Command Center shows:
- Application funnel (intake → documents → pre-audit → gaps → ready → submitted).
- Per-application confidence, gap list, and AI reasoning.
- One-click actions: request doc, approve phase, edit draft, convert to project.

---

## 9. Frontend Changes

### 9.1 Public intake portal (new)

`frontend/src/pages/ApplicationIntakePage.tsx`

- Multi-step wizard: organization → project basics → sector/methodology → document upload.
- Real-time AI suggestions (methodology recommendation after sector selection).
- Secure applicant dashboard to respond to AI requests.

### 9.2 Command Center Applications page (new)

`frontend/src/pages/command/ApplicationsPage.tsx`

- Table/kanban view of all applications.
- Detail drawer showing documents, gaps, AI drafts, and escalation history.
- Actions: send request, approve phase, convert to project, reject.

### 9.3 Validation workflow builder additions

- New step types in the palette: `application_intake`, `document_collection`, `document_ai_classification`, `methodology_match`, `gap_analysis`, `gap_remediation`, `applicant_interaction`, `promote_to_project`.
- Default template `ai_application_pipeline` available when creating a workflow.

---

## 10. API Additions

`backend/app/api/applications.py` — mounted at `/applications`:

- `POST /applications` — create application (public or authenticated).
- `GET /applications` — list for consultants.
- `GET /applications/{id}` — detail.
- `POST /applications/{id}/upload` — public upload endpoint tied to application token.
- `POST /applications/{id}/respond` — applicant response endpoint.
- `POST /applications/{id}/trigger-pipeline` — start/restart AI pipeline.
- `POST /applications/{id}/approve-phase` — consultant approval.
- `POST /applications/{id}/convert-to-project` — manual promotion.
- `GET /applications/{id}/gaps` — gap list.
- `GET /applications/public/{token}` — read-only applicant portal data.

---

## 11. Background Jobs

Add to `backend/app/tasks/application_jobs.py`:

- `process_application_pipeline` — Celery wrapper around `ValidationOrchestrator.execute_workflow()`.
- `poll_applicant_responses` — check for new email/cloud-storage/registry responses.
- `send_application_reminders` — nudge applicants for outstanding requests.
- `archive_stale_applications` — mark applications inactive after 90 days of no response.

Register tasks in `celery_app.py` include list and schedule daily reminders.

---

## 12. Security & Compliance

- Applicant emails are encrypted at rest with searchable hashes (same pattern as `User.email`).
- Public upload endpoints use time-limited signed tokens (JWT with 7-day expiry).
- All AI outputs are stored as proof artifacts in the validation engine.
- No AI-generated content is submitted to a registry without human approval.
- Audit logs record every AI decision, human override, and document access.

---

## 13. Testing Strategy

- **Unit:** New step executors with mocked Kimi and S3 responses.
- **Integration:** Full pipeline run against a seeded test application with sample documents.
- **E2E:** Playwright tests for the intake wizard and consultant applications page.
- **Contract:** Ensure new executors conform to `StepExecutor` interface.

---

## 14. Phased Implementation

**Phase 1 — Core intake and document collection (2–3 weeks)**
- `Application` model + API
- Public intake portal
- `application_intake`, `document_collection`, `document_ai_classification` executors
- Secure applicant upload token

**Phase 2 — Gap analysis and remediation (2–3 weeks)**
- `methodology_match`, `gap_analysis`, `gap_remediation`, `applicant_interaction` executors
- AI-generated gap lists and request emails
- Consultant Applications page

**Phase 3 — Promotion and downstream automation (2 weeks)**
- `promote_to_project` executor
- Trigger calculation and report generation
- Human approval gate before registry submission

**Phase 4 — Lead-to-application bridge (1–2 weeks)**
- Convert registry leads directly into applications
- Auto-ingest discovered documents
- Daily pipeline cron

---

## 15. Open Questions

1. Should the public intake portal require email verification before starting?
2. Which cloud storage providers must be supported in Phase 1?
3. Should the system charge applicants, or is intake free?
4. What is the target time-to-ready from first application submission?

---

## 16. Recommendation

Proceed with **Phase 1** first. It delivers the most visible value (a working AI intake portal) and provides the foundation for the remaining phases without disrupting existing project/calculation/report flows.
