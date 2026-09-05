# AI Application Pipeline

## Overview

The AI Application Pipeline lets project owners apply for carbon credit verification
directly on CarbonVerify, instead of waiting for a consultant to onboard them. The
pipeline automates the front of the audit funnel: intake, document collection, and
AI-led document classification — so scarce audit resources are only spent on
applications that are already document-complete and pre-classified.

Two ways applications enter the system:

1. **Direct applicant intake** — project owners fill in the public wizard at `/apply`.
2. **Consultant-initiated** — an operator submits intake on behalf of a client via the
   same API (`POST /applications`).

## How It Works

```
/apply (public wizard)
    │  POST /applications
    ▼
Application record (status: intake) + applicant JWT token
    │
    ▼
ai_application_pipeline  (validation workflow template)
    ├── Step 1: application_intake        → creates (or reuses) the Application
    │                                        record
    ├── Step 2: document_collection       → records expected document slots,
    │                                        status → documents_pending
    └── Step 3: document_ai_classification → Kimi AI classifies each uploaded
                                             document (pdd, monitoring_report,
                                             sales_receipt, ...) and extracts
                                             entities
```

Every step runs through the Workflow Validation Engine, so each execution produces
SHA-256 proof artifacts assembled into a Merkle tree and anchored to the Radix ledger.

## Public Intake

1. Visit `/apply` and complete the 3-step wizard (contact → project basics →
   sector/methodology).
2. On submit, the API creates the `Application` record, encrypts the applicant
   email at rest (Fernet + searchable HMAC hash), and returns a time-limited
   **applicant token** (7-day JWT).
3. The applicant receives a **welcome email** containing a secure link to the
   upload portal and uses it to upload documents and track progress.

## API

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/applications` | public | Submit intake application |
| GET | `/applications` | viewer+ | List/filter applications |
| GET | `/applications/{id}` | viewer+ | Get one application |
| PATCH | `/applications/{id}` | operator+ | Update application |
| DELETE | `/applications/{id}` | admin | Delete application |
| GET | `/applications/{id}/documents` | viewer+ | List application documents |
| POST | `/applications/{id}/documents` | applicant token | Upload a document (multipart; scanned by ClamAV, stored in S3, text extracted for AI classification) |
| GET | `/applications/{id}/portal` | applicant token | Applicant portal data (status, gap findings, document list) |
| POST | `/applications/{id}/trigger-pipeline` | operator+ | Create a `ValidationRun` against the `ai_application_pipeline` template and queue it via Celery |

## Applicant Upload Portal

Applicants follow the secure link from the welcome email:
`/apply/portal?application_id=<id>&token=<applicant-jwt>`.

- No account is required — the applicant JWT (7-day) authenticates every request.
- Uploaded documents are virus-scanned (ClamAV), stored in S3, and text-extracted
  (PDF, HTML, plain text, CSV, JSON) so the AI classification step can read them.
- After uploading, an operator triggers (or re-triggers) the pipeline; the portal
  then shows the status and any gap findings.
- An intake submitted directly at `/apply` is detected by the pipeline, which
  reuses the existing `Application` record instead of creating a duplicate.

## Gap Analysis

The `document_ai_classification` step compares the classified document types
against the workflow's `required_document_types` config (e.g. `["pdd"]` for the
default template). The results are stored on `application.gap_findings`:

```json
{
  "required": ["pdd"],
  "classified": ["pdd", "sales_receipt"],
  "missing": [],
  "has_gaps": false,
  "remediation": {}
}
```

- `has_gaps: true` → application status becomes `gaps`; each missing type gets a
  human-readable remediation hint in `remediation`, also shown on the portal.
- `has_gaps: false` → application status advances to `pre_audit`.

## Phase 3 (Roadmap)

- Automatic re-classification after new applicant uploads (today an operator
  re-triggers the pipeline from the portal or API).
- AI-drafted gap remediation beyond the per-type guidance text.

## Automation Levels

- **High-confidence** classifications auto-advance the application.
- **Medium-confidence** items enter the human review queue (Command Center).
- **Low-confidence** or missing documents trigger an applicant request for more
  evidence.

## Statuses

`intake → documents_pending → pre_audit → gaps → ready_for_calculation →
ready_for_review → approved / submitted / rejected`
