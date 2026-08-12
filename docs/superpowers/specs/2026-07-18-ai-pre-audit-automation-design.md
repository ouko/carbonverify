# AI Pre-Audit Automation Design

**Date:** 2026-07-18  
**Status:** Design proposal  
**Goal:** Automate discovery, ingestion, and AI-powered pre-audit analysis of carbon-credit opportunities from public registries so that CarbonVerify can shorten verification timelines and reduce auditor rework.

---

## 1. Problem Statement

Organizations wait months — sometimes years — to get carbon projects verified. A large portion of that delay is caused by incomplete or inconsistent project documentation (PDD, monitoring reports, baseline data, stakeholder evidence) reaching human auditors, who then spend most of their time asking for missing items rather than validating substance.

CarbonVerify already scrapes public registries for sales leads and already has a Workflow Validation Engine with an AI-evaluation step. The opportunity is to connect those capabilities: automatically discover pending/unaudited projects on registries, pull their available documents and metadata into CarbonVerify, run an AI pre-audit workflow, and surface a readiness score plus a concrete gap report before an auditor is assigned.

---

## 2. Current State

### 2.1 Lead Intelligence

- Scrapers exist for **Verra**, **Gold Standard**, and **CDM** (`backend/app/services/lead_intelligence/`).
- They collect project metadata (name, developer, country, methodology, status, crediting period, registry URL) into the `leads` table.
- A **stuck-score** algorithm prioritizes leads that have been stalled for a long time.
- Live scraping is fragile: Verra is Cloudflare-blocked, Gold Standard now requires auth, CDM works only with non-headless Chromium + stealth.
- There is **no automated lead → project conversion** and no document download today.

### 2.2 Workflow Validation Engine

- Workflows are JSON-defined directed graphs of steps stored in `validation_workflows.workflow_graph`.
- 11 step types exist; the most relevant for pre-audit are:
  - `ai_evaluation` — LLM scoring against a prompt and threshold.
  - `database_query` — verify required data exists.
  - `decision_gate` — rule-based gates with optional human approval.
  - `http_request` / `external_api` — fetch registry data.
  - `notification` — alert reviewers.
  - `subflow` — nest reusable workflows.
- Proof artifacts, Merkle-tree anchoring, and run history are already built in.
- A new **Validation Workflow Builder UI** lets operators create/edit workflows without JSON.

### 2.3 Project / Audit Workflow

- Projects progress through `onboarding → data_collection → calculation → review → submitted → verified → monitoring`.
- Documents are uploaded to S3 and processed into `DataSource` records.
- Calculation runs, reports, and VVB submissions are manually approved by auditors.
- The `HumanReviewQueue` and `HumanEscalation` systems route flagged items to humans.

---

## 3. Target Outcomes

1. **Discover** pending/registered projects on Verra, Gold Standard, and CDM that look ready (or nearly ready) for verification.
2. **Ingest** registry metadata and publicly available documents into CarbonVerify.
3. **Pre-audit** the package with an AI-driven validation workflow before human auditors touch it.
4. **Route** high-readiness projects to auditors; route low-readiness projects back to the project developer with a gap report.
5. **Learn** from auditor feedback so the pre-audit model improves over time.

---

## 4. Proposed Approaches

### 4.1 Option A — Lightweight Lead Scoring (fastest)

Add document-link extraction and an AI-generated **readiness score** to the existing `leads` table. No new project records are created. Sales/BD users see which scraped opportunities already look audit-ready.

**Pros:** Low blast radius; uses existing scrapers and UI; can ship quickly.  
**Cons:** Does not actually accelerate the audit workflow inside CarbonVerify; still manual conversion and document upload.

### 4.2 Option B — Lead → Pre-Audit Project Pipeline (recommended)

When a scraped lead crosses a readiness threshold, automatically create a CarbonVerify **Project** and **Project Documents** from the registry, then run a configurable **pre-audit validation workflow**. Auditors see a readiness score, a gap report, and the original evidence.

**Pros:** Directly shortens the audit loop; leverages existing project/upload/validation infrastructure; keeps a human approval gate before full audit engagement.  
**Cons:** Requires new backend jobs, scraper document extraction, and UI for reviewing pre-audit results.

### 4.3 Option C — Continuous Pre-Audit on All Projects (most comprehensive)

Attach a pre-audit validation workflow to **any** project and auto-trigger it whenever documents are uploaded or registry status changes. This turns the validation engine into a continuous compliance monitor.

**Pros:** Most powerful long-term; can catch gaps early in onboarding.  
**Cons:** Larger scope; risks noise if run on immature projects; should be layered on top of Option B rather than built from scratch.

**Recommendation:** Implement **Option B** first. It connects the existing lead scraper to the existing project and validation systems with a clear, bounded scope and measurable ROI.

---

## 5. Detailed Design — Option B

### 5.1 High-Level Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ Registry        │     │ Scraper +        │     │ Pre-audit           │
│ Portals         │────▶│ Document Fetcher │────▶│ Validation Workflow │
│ (Verra/GS/CDM)  │     │ (Celery job)     │     │ (AI + rule steps)   │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                                                            │
                                                            ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ Auditor         │◀────│ Human Review     │◀────│ Readiness Score +   │
│ Assignment      │     │ Queue            │     │ Gap Report          │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
```

### 5.2 New / Changed Components

| Component | Change | Files / Location |
|-----------|--------|------------------|
| `LeadDocument` model | New table storing links/hashes to registry documents discovered during scraping. | `backend/app/models.py` |
| Lead scrapers | Extract document URLs (PDD, monitoring reports, verification reports) where available. | `backend/app/services/lead_intelligence/*.py` |
| `RegistryDocumentFetcher` | New Celery task: download public PDFs/HTML, virus-scan, store in S3, create `FileUpload` + `DataSource`. | `backend/app/tasks/pre_audit_jobs.py` |
| `LeadToProjectConverter` | New Celery task / API: create `Project`, `FileUpload`, and `DataSource` records from a qualified lead. | `backend/app/api/leads.py`, `backend/app/tasks/pre_audit_jobs.py` |
| Pre-audit workflow template | New default workflow: document quality gate → data completeness → AI consistency check → decision gate. | `frontend/src/lib/validationWorkflowTemplates.ts`, `backend/app/validation_engine/templates/` |
| `PreAuditRun` bridge | Trigger validation run on project creation or document import; store readiness score on project. | `backend/app/api/validation_engine.py`, `backend/app/models.py` |
| Project pre-audit UI | New panel on `ProjectDetailPage` showing readiness score, gap report, and link to validation run detail. | `frontend/src/pages/ProjectDetailPage.tsx` |
| Auditor queue filters | New filters for `item_type = "pre_audit_gap"` or readiness thresholds. | `frontend/src/pages/ReviewQueuePage.tsx`, `command/InboxPage.tsx` |
| Feedback loop | Auditor resolution notes feed back to score confidence of future AI pre-audits. | `backend/app/services/lead_intelligence/scorer.py` |

### 5.3 Data Model Additions

```python
class LeadDocument(Base):
    """Documents discovered on a registry page for a lead."""
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    document_type: Mapped[str]  # e.g. "pdd", "monitoring_report", "verification_report"
    source_url: Mapped[str]
    title: Mapped[Optional[str]]
    file_hash_sha256: Mapped[Optional[str]]  # after download
    s3_key: Mapped[Optional[str]]
    s3_bucket: Mapped[Optional[str]]
    file_size_bytes: Mapped[Optional[int]]
    mime_type: Mapped[Optional[str]]
    file_upload_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("file_uploads.id"))
    status: Mapped[str] = mapped_column(default="discovered")  # discovered, fetched, failed
    error_message: Mapped[Optional[str]]
    fetched_at: Mapped[Optional[datetime]]
    fetch_attempts: Mapped[int] = mapped_column(default=0)
    last_fetch_attempt_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]

class ProjectPreAudit(Base):
    """Latest pre-audit result for a project."""
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("leads.id"))
    validation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("validation_runs.id"))
    readiness_score: Mapped[float]  # 0.0 - 1.0
    status: Mapped[str]  # passed, gaps, failed
    gap_summary: Mapped[Optional[dict]]
    created_at: Mapped[datetime]
```

### 5.4 Pre-Audit Workflow Template (default)

A new default workflow `pre_audit_document_package`:

1. **`http_request` / `external_api`** — fetch registry metadata and document list.
2. **`database_query`** — verify required project fields and data sources exist.
3. **`ai_evaluation`** — review PDD + monitoring report for completeness and consistency.
   - Prompt asks the LLM to return JSON: `score`, `gaps[]`, `risk_flags[]`, `recommendation`.
   - `pass_threshold`: 0.75.
4. **`decision_gate`** — if score ≥ 0.75 and no critical gaps, route to `ready_for_auditor`; else route to `gap_review`.
5. **`notification`** — on gaps, notify assigned operator with the gap report.

### 5.5 Trigger Logic

A new Celery beat task `run_pre_audit_pipeline` runs daily after `scrape_registries`:

```python
@shared_task
def run_pre_audit_pipeline():
    for lead in leads_ready_for_pre_audit():
        fetch_registry_documents.delay(lead.id)

@shared_task
def fetch_registry_documents(lead_id: UUID):
    # 1. download available docs
    # 2. create FileUpload + DataSource
    # 3. if enough docs, convert lead to project and run pre-audit
```

Conversion criteria (configurable):
- Lead status = `qualified` or `proposal_sent`.
- Readiness score from metadata-only heuristics ≥ 0.6.
- At least one downloadable document with status `fetched`.
- Lead has a non-empty `crediting_period_start` and `crediting_period_end` (required by the `Project` model).
- Lead has a mappable `methodology` value in `MethodologyEnum`.
- Not already converted.

Developer mapping: during conversion the system looks for an existing `Developer` record by email/domain. If none exists, it creates one using the lead's `project_developer`, `developer_contact`, and `developer_email` fields.

Human gate: even after auto-conversion, the project stays in `onboarding` status and the pre-audit result is surfaced in the review queue. An operator must explicitly move it to `data_collection` / `review`.

### 5.6 AI Prompt Strategy

The `ai_evaluation` step receives a prompt like:

```
You are a carbon credit verification pre-auditor. Review the following
Project Design Document (PDD) and monitoring report excerpts for the
project {project_name} using methodology {methodology}.

Evaluate against VCS/Gold Standard/CDM requirements for:
- Completeness of baseline scenario and additionality demonstration
- Clarity of monitoring plan and data sources
- Consistency between PDD and monitoring report
- Presence of stakeholder consultation evidence
- Compliance with methodology-specific requirements

Return strict JSON:
{
  "score": 0.0-1.0,
  "passed": true|false,
  "gaps": ["short description", ...],
  "risk_flags": ["high|medium|low: description", ...],
  "recommendation": "string"
}
```

Input data is passed via the workflow `variables` and `input_data` fields.

### 5.7 Readiness Score & Gap Report

After the workflow completes:

- `readiness_score` = weighted combination of:
  - AI evaluation score (60%)
  - Document completeness (25%)
  - Registry metadata completeness (15%)
- `gap_summary` = merged list from AI output and rule-based checks.
- `status` =
  - `passed` if score ≥ 0.80 and no critical risk flags
  - `gaps` if score ≥ 0.60 but < 0.80 or non-critical gaps exist
  - `failed` if score < 0.60 or critical risk flags exist

---

## 6. Registry-Specific Implementation Notes

### 6.1 Verra

- **Public API:** third-party scrapers (e.g., Apify) report an unauthenticated Verra project API exists. CarbonVerify's current Playwright scraper is Cloudflare-blocked.
- **Recommendation:** Prioritize finding/intercepting the Verra XHR API (the existing `playwright_utils.py` already intercepts API responses). If stable endpoints can be found, switch the Verra scraper from HTML parsing to API calls.
- **Documents:** project detail pages link to PDD and verification reports; document URLs can be extracted from the detail page or API response.

### 6.2 Gold Standard

- **API:** `api.goldstandard.org/projects` is the documented endpoint. The current scraper reports it now requires authentication.
- **Recommendation:** Investigate whether a public API key can be obtained, or fall back to the public Impact Registry pages with Playwright + stealth.
- **Documents:** Gold Standard public disclosure rules require project documents for each certification stage to be published; links are on project detail pages.

### 6.3 CDM

- **Current state:** CDM scraper works with non-headless Chromium.
- **Documents:** CDM project pages directly link to the PDD PDF and appendices. The scraper can be extended to capture these links.
- **Recommendation:** Extend the CDM parser to extract `project design document` and `validation report` links from the project detail/history pages.

---

## 7. User Workflow

1. **Operator** navigates to `Leads` and clicks **Run Scrape**.
2. Scrapers discover projects and their documents.
3. System downloads documents and creates `LeadDocument` records.
4. For leads that meet conversion criteria, the system creates a `Project`, uploads documents, and runs the pre-audit workflow.
5. **Operator** sees new projects in `Projects` with a **Pre-Audit** badge and readiness score.
6. Operator clicks into the project, reviews the gap report, and either:
   - Approves → project moves to `data_collection`/`review` and is assigned to an auditor.
   - Requests info → system generates a gap email to the developer.
   - Dismisses → project is archived.
7. **Auditor** receives a project that has already been document-checked, with a gap report and evidence hash chain.

---

## 8. Success Metrics

| Metric | How Measured | Target |
|--------|--------------|--------|
| Time from lead discovery to auditor assignment | Average days between `Lead.scraped_at` and project reaching `review` | Reduce by 40% |
| Auditor rework rate | % of projects sent back to developers for missing docs | Reduce by 50% |
| Pre-audit accuracy | % of AI-flagged gaps confirmed by auditor | ≥ 85% |
| Document coverage | % of converted projects with PDD + monitoring report fetched automatically | ≥ 70% |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Registry blocking/scraping fragility | Keep demo fallback; invest in API-first scraping for Verra/Gold Standard; use proxy rotation. |
| AI hallucinations in gap reports | Require human approval gate; use structured JSON output; ground prompts in extracted text; track auditor feedback. |
| Sensitive developer data in public docs | Only download publicly disclosed documents; respect robots.txt; store with existing encryption. |
| Noise in auditor queue | Only auto-convert high-readiness leads; allow operators to tune thresholds per registry. |
| Large PDF processing cost | Limit AI evaluation to extracted text chunks; cache results; run only on new/changed documents. |

---

## 10. Suggested Implementation Phases

### Phase 1 — Document Discovery (1-2 weeks)
- Add `LeadDocument` table.
- Extend CDM, Verra, and Gold Standard scrapers to extract document links.
- Add `fetch_registry_documents` Celery task to download and store docs.

### Phase 2 — Lead-to-Project Conversion (1-2 weeks)
- Add `convert_lead_to_project` task/API.
- Create default pre-audit workflow template.
- Run pre-audit workflow on converted projects and store `ProjectPreAudit`.

### Phase 3 — UI & Queue Integration (1-2 weeks)
- Add pre-audit panel to `ProjectDetailPage`.
- Add readiness score badges in project list.
- Add pre-audit filters to review queue.

### Phase 4 — Feedback Loop & Optimization (ongoing)
- Capture auditor confirmations/rejections of AI gaps.
- Tune prompts and thresholds.
- Add continuous pre-audit triggers on new document uploads.

---

## 11. Open Questions

1. Should auto-conversion create the project immediately, or should an operator click **Convert** after reviewing the lead?
2. Which registry should be prioritized if API access is required (Gold Standard) or pages are blocked (Verra)?
3. Should the pre-audit workflow run on **every** new project upload, or only on registry-imported projects?
4. How should the system handle projects that span multiple monitoring periods and therefore multiple monitoring reports?

---

## 12. References

- CarbonVerify Lead Intelligence: `backend/app/services/lead_intelligence/`
- CarbonVerify Validation Engine: `backend/app/validation_engine/`, `docs/WORKFLOW_VALIDATION_ENGINE.md`
- CarbonVerify Project/Upload flow: `backend/app/api/projects.py`, `backend/app/api/uploads.py`
- Verra Registry: https://registry.verra.org/
- Gold Standard Impact Registry: https://www.goldstandard.org/project-developers/impact-registry
- UNFCCC CDM Project Search: https://cdm.unfccc.int/Projects
