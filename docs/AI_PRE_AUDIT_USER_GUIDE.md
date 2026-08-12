# AI Pre-Audit User Guide

**Purpose:** Use CarbonVerify to discover carbon-credit opportunities on public registries, gather their available documents, and run AI-assisted pre-audit checks so that human auditors spend less time chasing missing paperwork and more time validating substance.

**Audience:** Operators, auditors, and project managers who want to shorten verification timelines.

---

## What this guide covers

1. The pre-audit concept
2. What CarbonVerify can do today
3. Recommended manual workflow (now)
4. Automated workflow (coming next)
5. Interpreting AI pre-audit results
6. Best practices

---

## 1. The pre-audit concept

A traditional audit flow looks like this:

```
Project developer submits documents
        ↓
Auditor reviews and finds gaps
        ↓
Developer fixes gaps
        ↓
Auditor reviews again
        ↓
Report submitted to registry
```

The biggest delays happen in the first two steps: documents are incomplete, inconsistent, or missing required sections, and the auditor spends days identifying those gaps.

A **pre-audit** flips this around:

```
CarbonVerify discovers project on registry
        ↓
Public documents are pulled automatically
        ↓
AI checks completeness + consistency
        ↓
Gap report is produced
        ↓
Developer fixes gaps BEFORE auditor assignment
        ↓
Auditor receives a clean, pre-checked package
```

Result: fewer back-and-forth cycles, faster verification, and lower cost for both auditors and project developers.

---

## 2. What CarbonVerify can do today

### 2.1 Discover opportunities on registries

CarbonVerify can scrape three major carbon registries:

- **Verra (Verified Carbon Standard)**
- **Gold Standard**
- **UNFCCC CDM (Clean Development Mechanism)**

To run a scrape:

1. Log in as an **operator** or **admin**.
2. Go to **Core → Lead Intelligence**.
3. Click **Run Scrape**.
4. The system will contact each registry and create/update `Lead` records.

Each lead shows:
- Project name, developer, country, methodology
- Registry status (e.g., "under validation", "registered", "verification pending")
- Crediting period and last verification date
- A **stuck score** that tells you how long the project has been stalled

> **Note:** Live scraping can be blocked by registry anti-bot protection. If a registry blocks the request, CarbonVerify falls back to representative demo data so the UI still works. Set `LEAD_SCRAPER_MODE=live` in your environment to attempt live scraping.

### 2.2 Review and prioritize leads

The Lead Intelligence page has two views:

- **Table view** — sort and filter by registry, priority, status, or country.
- **Kanban view** — move leads through `new → contacted → qualified → proposal_sent → converted`.

Use the stuck score and priority to decide which projects are worth pursuing. High stuck-score projects are usually the ones that have been waiting longest for verification help.

### 2.3 Build validation workflows with AI evaluation

CarbonVerify includes a **Workflow Validation Engine**. You can create workflows that:

- Fetch data from APIs or databases
- Run rule-based decision gates
- Call the Kimi AI for document evaluation
- Generate proof artifacts and audit trails

To create a pre-audit workflow:

1. Go to **Core → Workflow Builder**.
2. Click **New Workflow** or start from the **Document quality gate** template.
3. Add an `AI Evaluation` step.
4. In the step config, write a prompt that asks the AI to review a Project Design Document (PDD) or monitoring report for completeness.
5. Set a **pass threshold** (e.g., `0.75`).
6. Wire the success path to `end` and the failure path to a `Notification` step or another `AI Evaluation`.
7. Save the workflow.

Example prompt:

```text
Review the following Project Design Document for completeness against
VCS/Gold Standard/CDM requirements. Evaluate:
- Baseline scenario and additionality demonstration
- Monitoring plan and data sources
- Stakeholder consultation evidence
- Methodology-specific requirements

Return strict JSON:
{
  "score": 0.0-1.0,
  "passed": true|false,
  "gaps": ["short description", ...],
  "risk_flags": ["description", ...],
  "recommendation": "string"
}
```

### 2.4 View and fetch registry documents

When a lead is scraped, CarbonVerify attempts to discover publicly available documents on the registry project page:

- Project Design Document (PDD)
- Monitoring reports
- Verification / validation reports

To see discovered documents:

1. Open a lead's detail modal in **Lead Intelligence**.
2. Scroll to the **Documents** section.
3. Each document shows its type, title, status (`discovered`, `fetched`, `failed`), and a link to the original registry URL.

To download documents into CarbonVerify:

1. Click **Fetch Documents** in the documents section.
2. The system queues an async job that downloads each document, scans it, stores it in S3, and records its SHA-256 hash.
3. Refresh the modal to see updated `fetched` statuses.

Fetched documents can later be converted into project `FileUpload` / `DataSource` records when the lead is promoted to a project.

### 2.5 Run a workflow against a project

Once a workflow exists, you can trigger it:

1. Go to the workflow detail or run history page.
2. Click **Run Workflow**.
3. Select the project and provide any input data (e.g., document IDs, registry URLs).
4. The run executes asynchronously. You can watch the steps complete and review proofs.

The workflow produces:
- A pass/fail result
- Step-by-step execution log
- Proof artifacts (hashed and anchored)
- AI evaluation request/response records

---

## 3. Recommended manual workflow today

Until the fully automated pipeline is implemented, you can use CarbonVerify's existing features to run an AI pre-audit manually:

### Step 1 — Scrape registries

Run **Lead Intelligence → Run Scrape** daily or weekly. Focus on projects whose status indicates they are pending validation or verification.

### Step 2 — Qualify leads

In the Lead Intelligence page:

- Filter for high priority / high stuck-score leads.
- Open the lead detail modal.
- Review discovered documents in the **Documents** section; click **Fetch Documents** to download them.
- Move promising leads to `qualified` or `proposal_sent`.

### Step 3 — Create a project

When a lead is qualified, create a CarbonVerify project:

1. Copy the project name, methodology, crediting period, and country from the lead.
2. Go to **Projects → New Project**.
3. Fill in the project details and save.

### Step 4 — Upload available documents

Documents discovered in the lead modal can be downloaded from their source URLs. You can also download public documents directly from the registry URL:

- PDD / Project Design Document
- Monitoring reports
- Verification reports
- Stakeholder consultation records

Then upload them to the project:

1. Open the project detail page.
2. Go to **Documents** or **Data Sources**.
3. Upload each file. CarbonVerify will virus-scan, hash, and store them in S3.
4. The system creates `DataSource` records for further processing.

> **Tip:** After Phase 2 is implemented, fetched lead documents will be converted into project documents automatically when a lead is promoted.

### Step 5 — Run the pre-audit workflow

1. Go to **Core → Workflow Builder**.
2. Open your pre-audit workflow.
3. Click **Run Workflow**.
4. Select the project you just created.
5. The AI evaluation step reads the uploaded documents and returns a score + gap list.

### Step 6 — Review results and act

Open the run detail page:

- If the workflow **passed** and the score is high, move the project to `review` and assign an auditor.
- If the workflow found **gaps**, export the gap report and send it to the project developer. Wait for corrected documents, then re-run the workflow.
- If the workflow **failed**, archive the project or keep it as a low-priority lead.

---

## 4. Automated workflow

Phase 1 (document discovery and download) and Phase 2 (lead-to-project conversion and AI pre-audit) are now implemented. The automated workflow is:

1. **Run scrape** — `Lead Intelligence → Run Scrape` discovers projects and their public documents.
2. **Fetch documents** — The system downloads each discovered document, virus-scans it, stores it in S3, and records its SHA-256 hash.
3. **Auto-convert qualified leads** — For leads that are `qualified` or `proposal_sent`, have crediting-period dates, have at least one fetched document, and are not already converted, the system creates a CarbonVerify `Project` and imports the fetched documents as `FileUpload` / `DataSource` records.
4. **Run pre-audit** — The default `pre_audit_document_package` validation workflow runs against the converted project. It checks document presence, extracts text excerpts, and asks the Kimi AI to evaluate completeness and consistency.
5. **Review readiness badge** — Open the project detail page to see the **readiness score** and **gap report**.
6. **Operator decision** — Projects start in `onboarding`. An operator must explicitly approve before the project moves to `data_collection` / `review`.

You can also trigger conversion and pre-audit manually for a single lead:

1. Open **Lead Intelligence**.
2. Find a lead with fetched documents.
3. Call `POST /leads/{lead_id}/convert-and-pre-audit` (operator role required).
4. The system returns the `ProjectPreAudit` result, and the new project appears in **Projects**.

The daily scrape job (`scrape_registries`) queues the pre-audit pipeline automatically, so the nightly workflow is fully hands-off.

### 4.1 Targeting unaudited / pending-validation opportunities

By default, the scraper imports projects in any status. To focus on the projects where pre-audit saves the most time, configure the pipeline to target *pending* statuses:

1. Open `backend/.env` (or your deployment environment).
2. Ensure `LEAD_SCRAPER_MODE=live`.
3. (Optional) Set registry-specific status filters if they are exposed in your deployment's scraper configuration.
4. Run **Lead Intelligence → Run Scrape**.
5. Sort the lead table by **Status** and look for:
   - Verra: `under_validation`, `under_verification`, `registration_requested`, `under_development`
   - Gold Standard: `under_validation`, `under_certification`
   - CDM: `validation`, `registration_requested`

For a deeper optimization roadmap — including the Verra UI API, incremental document fetching, batch AI evaluation, and third-party aggregator integrations — see [`docs/PRE_AUDIT_OPTIMIZATION.md`](./PRE_AUDIT_OPTIMIZATION.md).

### 4.2 Consultant workflow: introduce projects from a registry

If you are a consultant who wants to pull projects from a registry, import their documents, and see what is missing before an auditor is assigned:

1. **Scrape the registry.** Go to **Core → Lead Intelligence → Run Scrape**. Select the registry and target country.
2. **Filter for unaudited projects.** Use the status filters above, or sort by **stuck score** to find projects that have been waiting longest.
3. **Fetch documents.** Open a lead, scroll to **Documents**, and click **Fetch Documents**. The system downloads PDDs, monitoring reports, validation reports, etc., virus-scans them, and stores them in S3.
4. **Convert and pre-audit.** With the lead selected, call `POST /leads/{lead_id}/convert-and-pre-audit` (operator role required). The system creates a CarbonVerify `Project`, imports the fetched documents as `FileUpload` / `DataSource` records, and runs the default `pre_audit_document_package` workflow.
5. **Review the result.** Open **Projects → {project}**. The **Pre-Audit** panel shows:
   - Readiness score (0.00 – 1.00)
   - Status badge (`passed`, `gaps`, or `failed`)
   - Gap list and risk flags
   - AI recommendation
6. **Act on gaps.** Export the gap report, request corrected documents from the project developer, and re-run the workflow. Once the score is ≥ 0.80 and no critical risk flags remain, assign an auditor.

---

## 5. Interpreting AI pre-audit results

### Readiness score

| Score | Meaning | Suggested action |
|-------|---------|------------------|
| 0.80 – 1.00 | Strong package, few or no gaps | Assign to auditor |
| 0.60 – 0.79 | Usable but has gaps | Request corrections first |
| 0.00 – 0.59 | Major issues or missing documents | Reconsider engagement or ask for full resubmission |

### Gap types

- **Completeness gaps** — required sections missing from PDD/monitoring report.
- **Consistency gaps** — numbers or statements contradict each other across documents.
- **Methodology gaps** — project does not fully follow the claimed methodology.
- **Evidence gaps** — stakeholder consultation, baseline data, or monitoring evidence is missing.

### Risk flags

Risk flags highlight issues that are likely to cause auditor pushback even if the score is passing. Always review risk flags before assigning an auditor.

---

## 6. Best practices

- **Run scrapes regularly.** Registries update project statuses daily. A project that was "under validation" yesterday may have published new documents today.
- **Prioritize by stuck score, not just size.** A small project that has been stuck for 18 months may convert faster than a large one stuck for 3 months.
- **Always verify AI output.** AI pre-audit is a triage tool, not a substitute for human judgment. Auditors must still perform substantive review.
- **Keep prompts versioned.** As methodologies and registry rules change, update the AI evaluation prompt and save a new workflow version.
- **Feed back auditor decisions.** When an auditor confirms or rejects an AI-flagged gap, record that. It improves future pre-audit accuracy.
- **Respect registry terms.** Only download publicly disclosed documents. Do not hammer registry servers with rapid requests; use the built-in daily scheduling.

---

## 7. Related documentation

- `docs/WORKFLOW_VALIDATION_ENGINE.md` — technical details of the validation engine
- `docs/superpowers/specs/2026-07-18-ai-pre-audit-automation-design.md` — implementation design spec
- `AGENTS.md` — development commands and environment setup

---

## 8. Getting help

If a registry scrape consistently fails:

1. Check **Lead Intelligence → Scraper Health**.
2. Review logs in `.local-logs/celery-worker.log`.
3. Try switching `LEAD_SCRAPER_MODE` between `live` and `demo`.
4. Ensure Playwright and Chromium are installed if running outside Docker.
