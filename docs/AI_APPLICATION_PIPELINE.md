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
    ├── Step 1: application_intake        → creates the Application record
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
3. The applicant later uses the token-backed secure link to upload documents and
   track progress (upload portal ships in Phase 2).

## API

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/applications` | public | Submit intake application |
| GET | `/applications` | viewer+ | List/filter applications |
| GET | `/applications/{id}` | viewer+ | Get one application |
| PATCH | `/applications/{id}` | operator+ | Update application |
| DELETE | `/applications/{id}` | admin | Delete application |
| GET | `/applications/{id}/documents` | viewer+ | List application documents |
| POST | `/applications/{id}/trigger-pipeline` | operator+ | Run the AI pipeline for the application |

## Automation Levels

- **High-confidence** classifications auto-advance the application.
- **Medium-confidence** items enter the human review queue (Command Center).
- **Low-confidence** or missing documents trigger an applicant request for more
  evidence.

## Statuses

`intake → documents_pending → pre_audit → gaps → ready_for_calculation →
ready_for_review → approved / submitted / rejected`

## Phase 2 (Roadmap)

- End-to-end pipeline execution from the trigger endpoint (create/run `ValidationRun`
  against the `ai_application_pipeline` template).
- Secure document upload portal using the applicant token.
- Gap analysis (`gap_findings`) and AI-drafted remediation guidance for applicants.
- Email notifications with the secure upload link.
