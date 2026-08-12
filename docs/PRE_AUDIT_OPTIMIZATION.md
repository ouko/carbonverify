# Pre-Audit Automation — Optimization & Data-Source Guide

> **Audience:** Consultants, operators, and auditors who want to maximize the number of pending/under-audited carbon projects that CarbonVerify can discover, import, and pre-check automatically.

## Goal of this guide

CarbonVerify's AI pre-audit pipeline already converts qualified registry leads into projects and runs a default validation workflow. This document explains how that pipeline can be **optimized** to focus on *unaudited* or *pending-validation* opportunities, where the time savings for auditors are largest, and how to configure the system to use the best available data source for each registry.

---

## 1. What "pending unaudited" means

The biggest delay in verification is usually the first validation cycle. Projects in these statuses are the highest-value targets:

| Registry | High-value statuses | Meaning |
|----------|---------------------|---------|
| **Verra VCS** | `Under Development`, `Under Validation`, `Registration Requested`, `Under Verification` | Project has submitted documents or is awaiting/under VVB review [[Verra registration process]](https://verra.org/wp-content/uploads/2023/08/Registration-and-Issuance-Process-v4.4-last-updated-4-Oct-2023-watermark.pdf) |
| **Gold Standard** | `under_validation`, `under_certification` | Project has not yet received final certification [[Gold Standard certification process]](https://www.goldstandard.org/publications/certification-process-stepbystep) |
| **UNFCCC CDM** | `validation`, `registration requested` | Project is in the DOE validation or EB registration queue [[CDM project activities]](https://cdm.unfccc.int/Projects) |

Projects that are already `registered` or `certified` have passed validation; pre-auditing them adds less value unless they are about to enter a *monitoring/verification* cycle.

---

## 2. Registry data sources — current options

### 2.1 Verra (VCS)

Verra's public registry exposes two useful endpoints used by the Angular search UI:

- Project search: `POST https://registry.verra.org/uiapi/resource/resource/search`
- Project summary: `GET https://registry.verra.org/uiapi/resource/resourceSummary/{id}`

The search endpoint accepts a JSON body such as:

```json
{
  "program": "VCS",
  "resourceClass": "project",
  "resourceStatuses": ["VCS_EX_UNDER_VALIDATION", "VCS_EX_UNDER_DEVELOPMENT_CLD"],
  "$skip": 0,
  "$top": 100
}
```

These endpoints are unauthenticated and have been observed returning full project listings in third-party scrapers [[Verra AFOLU explorer]](https://sovereignratings.yashmoitra.com/verra.html) and Apify actors [[Apify Verra scraper]](https://apify.com/jungle_synthesizer/carbon-credit-registry-scraper). However, Verra also uses Cloudflare bot protection, so direct `curl` calls from an unknown IP often return an HTML challenge page rather than JSON.

**Recommendation:**
- Use the UI API in preference to full Playwright page interaction when possible — it is faster and more reliable.
- If the API returns a Cloudflare challenge, fall back to the existing Playwright path but seed the API call with cookies from a short Playwright session.
- Filter by the status values above so only high-value pipeline projects are imported.

### 2.2 Gold Standard

Gold Standard hosts project documentation on the **Impact Registry** (`registry.goldstandard.org`) and underlying project data in the **SustainCERT App**. The public project API used by the current scraper (`https://api.goldstandard.org/projects`) now returns:

```json
{"message":"Can only accept requests of type: authenticated"}
```

This is confirmed by the scraper's own live tests. Gold Standard's public Impact Registry pages can still be reached with Playwright, but structured data requires an authenticated account or an approved API integration [[Gold Standard Impact Registry]](https://www.goldstandard.org/project-developers/impact-registry).

**Recommendation:**
- Apply for Gold Standard API credentials if you plan to scale beyond demo data.
- Until credentials are available, rely on Playwright document parsing and accept that only project detail pages (not bulk search results) will be reliable.
- Prioritize leads whose detail pages list a PDD and validation report.

### 2.3 UNFCCC CDM

The CDM is a legacy Kyoto mechanism. New project submissions essentially stopped after 2020, but a large backlog of registered projects still undergoes monitoring and verification. The UNFCCC site publishes project detail and history pages, and the UNEP DTU CDM Pipeline historically provided a monthly Excel workbook with status, host country, methodology, and emission-reduction estimates for ~12,000 projects [[UNEP DTU CDM Pipeline dataset]](https://data.dtu.dk/articles/online_resource/CDM_Pipeline_Analysis_and_Database/7667633).

**Recommendation:**
- Do not rely on CDM for *new* unaudited opportunities.
- Use CDM mainly for legacy project due-diligence or for registered projects about to enter a verification cycle.

### 2.4 Third-party aggregators

If registry-level scraping remains fragile, commercial/aggregated APIs can be used as a secondary source:

| Service | Strength | Cost / Access |
|---------|----------|---------------|
| **Carbonmark API** | Unified REST search by country, category, vintage, registry | Public, free tier available [[docs]](https://docs.carbonmark.com/carbonmark-api/explore-carbon-projects/find-carbon-projects-by-methodology-category) |
| **VCM.fyi API** | Clean project metadata across registries | Requires Pro/Enterprise API key [[quickstart]](https://docs.api.vcm.fyi/quickstart) |
| **Allied Offsets** | Large aggregated dataset, includes ratings | Paid subscription |
| **Apify actors** | Ready-made Verra/Gold Standard scrapers | Usage-based, requires Apify account [[actor]](https://apify.com/jungle_synthesizer/carbon-credit-registry-scraper) |

**Recommendation:**
- Keep the built-in registry scrapers as the primary source (no extra cost, no external dependency).
- Add a Carbonmark integration as a fallback/enrichment source to fill missing methodology or country fields.
- Use VCM.fyi or Allied Offsets only if you need ratings or retirement data for prioritization.

---

## 3. Workflow optimizations

### 3.1 Scrape only the highest-value statuses (implemented)

The daily `run_pre_audit_pipeline` task can be restricted to leads whose registry status is pending/under audit. Set in `backend/.env`:

```bash
PRE_AUDIT_PENDING_ONLY=true
PRE_AUDIT_PENDING_STATUSES=under_validation,under_verification,under_certification
```

When `PRE_AUDIT_PENDING_ONLY=true`, only leads with one of those statuses and at least one fetched document are converted and pre-audited. The default statuses cover the registries’ high-value pipeline states:

| Registry | Mapped status values |
|----------|----------------------|
| Verra VCS | `under_validation`, `under_verification`, `under_certification` (store these strings in the lead `status` field) |
| Gold Standard | `under_validation`, `under_certification` |
| CDM | `validation`, `registration requested` |

If your registry source emits different status strings, add them to the comma-separated list. This avoids converting already-registered projects and wasting AI tokens on projects that do not need pre-audit help.

### 3.2 Incremental document fetching (implemented)

`RegistryDocumentFetcher` stores `etag` and `last_modified` headers on each `LeadDocument`. On subsequent fetches it sends:

```http
If-None-Match: <stored etag>
If-Modified-Since: <stored last_modified>
```

If the registry returns `304 Not Modified`, the document is marked `fetched` again but no S3 upload or virus scan runs. The existing `file_hash_sha256` still deduplicates identical content if the registry does not support conditional requests.

This is automatic; no configuration is required. It reduces bandwidth, S3 writes, and virus-scanning load on nightly re-scrapes.

### 3.3 Batch and prioritize AI evaluation

The default `pre_audit_document_package` workflow evaluates one project per run. At scale, consider:

- **Parallel document extraction:** `_build_document_excerpts` fetches and extracts each document sequentially. Use `asyncio.gather` with a semaphore to run extraction in parallel.
- **Chunked prompt strategy:** If a project has many documents, summarize each document individually, then pass the summaries to the final evaluator. This keeps the prompt within the model context window and reduces per-token cost.
- **Priority queue:** Give `qualified` leads with high `stuck_score` a higher Celery priority so auditors see the most stalled projects first.

### 3.4 Watchlist / change detection (implemented)

Converted projects are re-audited only when their fetched documents actually change. The `Lead` model stores a `document_fingerprint` — a SHA-256 hash of each fetched document's `source_url` and `file_hash_sha256`. The daily `re_audit_changed_projects` task:

1. Refreshes documents for every converted lead.
2. Computes the current fingerprint.
3. If it differs from the stored fingerprint (or no fingerprint exists), it queues `run_pre_audit_for_project` and updates the stored fingerprint.

This turns the pipeline from *scan everything daily* into a *change-driven* workflow, saving AI tokens and auditor review time.

### 3.5 Use the API-first path when available

A future scraper refactor could look like:

```
scrape_registries
    ├─ Verra:  try UI API → fallback Playwright
    ├─ Gold Standard: try authenticated API → fallback Playwright detail pages
    └─ CDM:    Playwright detail pages (legacy, low priority)
```

Keep the existing Playwright fallback so demo mode and blocked networks still work.

---

## 4. Recommended user workflow for a consultant

If you are a consultant evaluating whether CarbonVerify can help a portfolio of projects, use this workflow:

1. **Set scope filters.** In `backend/.env` set:
   ```bash
   PRE_AUDIT_PENDING_ONLY=true
   PRE_AUDIT_PENDING_STATUSES=under_validation,under_verification,under_certification
   LEAD_SCRAPER_MODE=live   # or demo for testing
   ```
2. **Start the stack.** With Docker Compose or `./scripts/start-local.sh`, ensure Celery worker and beat are running. Beat automatically schedules the pre-audit tasks daily.
3. **Import known projects** (optional). If you already have a list of registry IDs or URLs, call the bulk-import endpoint:
   ```bash
   curl -X POST http://localhost:8000/leads/bulk-import \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "registry_source": "cdm",
       "items": [
         {"external_id": "1234", "project_name": "Project A"},
         {"external_id": "5678", "registry_url": "https://cdm.unfccc.int/5678"}
       ]
     }'
   ```
   The endpoint creates (or updates) the leads and queues document fetching. The response includes `lead_id`s you can check in the UI.
4. **Fetch documents** for the top leads, either manually via the Lead Intelligence UI (`POST /leads/{lead_id}/fetch-documents`), via the bulk import above, or by waiting for the nightly `fetch-all-pending-documents` task. Confirm that PDDs/validation reports are publicly available.
5. **Convert and pre-audit.** Either call `POST /leads/{lead_id}/convert-and-pre-audit` for a lead you want to evaluate immediately, or wait for the nightly `run-pre-audit-pipeline` task.
6. **Open Projects → detail page.** Read the readiness score and gap report.
7. **Export the gap report** and share it with the project developer. Once corrected documents are uploaded, the nightly `re-audit-changed-projects` task will re-score the project automatically.
8. **Assign an auditor** only after the project reaches a passing readiness score or the flagged gaps are acceptable.

The daily automation is:

```
scrape-registries
    ↓
fetch-all-pending-documents
    ↓
run-pre-audit-pipeline  (converts & pre-audits qualified pending leads)
    ↓
re-audit-changed-projects  (re-scores converted projects with changed docs)
```

---

## 5. Implementation priority

The following optimizations are already implemented:

1. ✅ **Status filtering** — `PRE_AUDIT_PENDING_ONLY` / `PRE_AUDIT_PENDING_STATUSES`.
2. ✅ **Incremental document fetch** — `etag` / `last_modified` conditional requests.
3. ✅ **Change-driven re-audit** — `document_fingerprint` + `re_audit_changed_projects`.
4. ✅ **Parallel document extraction** — `PreAuditRunner._build_document_excerpts` runs up to 5 concurrent workers.
5. ✅ **Scheduled automation** — `fetch_all_pending_documents`, `run_pre_audit_pipeline`, and `re_audit_changed_projects` run daily in Celery Beat.

Additional improvements already implemented:

- ✅ **Consultant bulk-import endpoint** — `POST /leads/bulk-import` accepts a registry source and list of external IDs/URLs, creates or updates leads, and queues document fetching. See the consultant workflow above for the curl example.

Remaining improvements to consider next:

1. **Verra UI API integration** — reduces Playwright fragility.
2. **Gold Standard API credentials** — unlocks structured data for the registry that currently blocks unauthenticated requests.
3. **Dashboard widget** — show pending unaudited opportunities, fetched-document status, and readiness scores in one view.

---

## 6. References

- Verra Registration and Issuance Process v4.4 — https://verra.org/wp-content/uploads/2023/08/Registration-and-Issuance-Process-v4.4-last-updated-4-Oct-2023-watermark.pdf
- Verra public project summary endpoint example — https://registry.verra.org/uiapi/resource/resourceSummary/3628 (used by the Angular UI; may require a browser session) [[Stack Overflow discussion]](https://stackoverflow.com/questions/73552959/web-scraping-problem-when-scraping-different-projects)
- Gold Standard certification step-by-step — https://www.goldstandard.org/publications/certification-process-stepbystep
- Gold Standard Impact Registry — https://www.goldstandard.org/project-developers/impact-registry
- UNFCCC CDM project activities — https://cdm.unfccc.int/Projects
- UNEP DTU CDM Pipeline dataset — https://data.dtu.dk/articles/online_resource/CDM_Pipeline_Analysis_and_Database/7667633
- Carbonmark API docs — https://docs.carbonmark.com/carbonmark-api/explore-carbon-projects/find-carbon-projects-by-methodology-category
- VCM.fyi API quickstart — https://docs.api.vcm.fyi/quickstart
- Apify Verra / Gold Standard scraper — https://apify.com/jungle_synthesizer/carbon-credit-registry-scraper
