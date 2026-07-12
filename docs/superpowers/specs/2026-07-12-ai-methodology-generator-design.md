# AI-Driven Custom Methodology Generator

## Background

CarbonVerify helps project developers prepare MRV documentation for carbon credit verification. Many innovative projects—especially in emerging sectors such as regenerative agriculture hybrids, novel industrial processes, community-based blue carbon, or integrated waste-to-energy systems—do not map cleanly onto an existing Verra or Gold Standard methodology. When no approved methodology exists, the project cannot proceed to validation until a new methodology is developed, a process that typically takes 12–24 months and requires specialized carbon accounting expertise.

Verra’s [Methodology Development and Review Process](https://verra.org/program-methodology/vcs-program-standard/develop-new-methodology/) (MDRP) defines the stages: Methodology Idea Note → Methodology Concept Note → Draft Methodology → Public Consultation → Independent Expert Review → Final Verra Review. Gold Standard publishes similar [Requirements for Methodology Development](https://www.goldstandard.org/consultations/requirements-for-methodology-development). A credible methodology must, at minimum, define scope/applicability, baseline scenario, project scenario, additionality demonstration, GHG quantification equations, leakage assessment, monitoring parameters and data sources, uncertainty treatment, and safeguards/co-benefits.

## Problem Statement

Project developers using CarbonVerify need a way to:

1. Determine whether their project genuinely cannot use an existing methodology.
2. Receive a structured, registry-aligned draft methodology for the unique activity.
3. Translate that methodology into a quantification model that CarbonVerify can execute.
4. Track review, revision, and approval of the draft before external submission.

## Goals

- Build an **AI-assisted custom methodology generator** that produces a registry-ready draft methodology for projects that do not fit existing methodologies.
- Provide a **structured gap analysis** comparing the project against existing `MethodologyVersion` records and known registry methodologies.
- Generate a **quantification scaffold** (equations, parameters, data sources) that the existing calculation engine can ingest.
- Support a **human-in-the-loop review workflow** (draft → under review → approved → rejected) with audit logging.
- Expose the feature through the existing React frontend as a new wizard-driven page.

## Non-Goals

- Fully automated submission to Verra/Gold Standard registries. Human review and external submission remain required.
- Guaranteed approval by a registry. The generator produces a draft that accelerates development; approval is outside our control.
- Replacing existing approved methodologies. The feature is for projects that cannot use an approved methodology.
- Real-time public consultation or independent expert review tooling. The first version tracks status and comments only.

## Design Overview

The feature adds a new domain called `methodology_generator` to the backend and a new `MethodologyDesigner` page to the frontend.

### Backend

1. **Data model** — `GeneratedMethodology` table linked to `Project`.
2. **Gap analyzer** — compares project attributes against existing `MethodologyVersion` records and a curated knowledge base of registry scopes.
3. **AI generator service** — uses the existing `KimiAPIClient` to produce structured methodology sections and a quantification scaffold.
4. **API router** — `/methodology-generator/*` endpoints for create, analyze, generate, list, get, update status, and export.
5. **Review workflow** — status transitions with audit logging via `AuditLogger`.

### Frontend

1. **MethodologyDesigner page** — multi-step wizard collecting project context.
2. **GapAnalysis view** — shows why existing methodologies do not fit.
3. **DraftReview view** — renders the generated methodology sections and quantification scaffold.
4. **Status actions** — Submit for review, Approve, Reject, Request revisions.

### Integration

- Generated quantification scaffolds are stored as JSON and can be loaded into the existing `/calculations/` pipeline as a `CalculationRun` of type `custom_methodology`.
- Approved generated methodologies are optionally promoted to `MethodologyVersion` records for reuse across projects.

## Data Model

```sql
-- New table: generated_methodologies
CREATE TABLE generated_methodologies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    sector VARCHAR(100) NOT NULL,
    activity_description TEXT NOT NULL,
    boundaries_json JSONB NOT NULL DEFAULT '{}',
    data_sources_json JSONB NOT NULL DEFAULT '[]',
    gap_analysis_json JSONB,
    methodology_json JSONB,              -- structured draft methodology
    quantification_scaffold_json JSONB,  -- equations, params, monitoring plan
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    rejection_reason TEXT,
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_generated_methodologies_project_id ON generated_methodologies(project_id);
CREATE INDEX idx_generated_methodologies_status ON generated_methodologies(status);
```

### Pydantic schema

```python
class GeneratedMethodologyBase(BaseModel):
    name: str
    sector: str
    activity_description: str
    boundaries: dict
    data_sources: list

class GeneratedMethodologyCreate(GeneratedMethodologyBase):
    project_id: UUID

class GeneratedMethodologyOut(GeneratedMethodologyBase):
    id: UUID
    project_id: UUID
    gap_analysis: Optional[dict]
    methodology: Optional[dict]
    quantification_scaffold: Optional[dict]
    status: str
    rejection_reason: Optional[str]
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    created_by: UUID
    created_at: datetime
    updated_at: datetime

class MethodologyStatusUpdate(BaseModel):
    status: Literal["draft", "under_review", "approved", "rejected", "revision_requested"]
    rejection_reason: Optional[str] = None
```

## API Endpoints

All endpoints require a logged-in user. Status-changing endpoints require `operator` or `admin`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/methodology-generator/` | Create a new generated methodology record. |
| GET | `/methodology-generator/` | List records for the user/organization. |
| GET | `/methodology-generator/{id}` | Get a single record. |
| POST | `/methodology-generator/{id}/analyze` | Run gap analysis against existing methodologies. |
| POST | `/methodology-generator/{id}/generate` | Generate draft methodology and quantification scaffold. |
| PATCH | `/methodology-generator/{id}/status` | Update review status. |
| POST | `/methodology-generator/{id}/export` | Export draft as Markdown/JSON for registry submission. |
| POST | `/methodology-generator/{id}/promote` | (Admin) Copy approved draft into `MethodologyVersion`. |

## AI Generator Design

The generator uses the existing `KimiAPIClient.chat_completion`. The prompt is split into two calls for reliability:

### Call 1: Gap analysis

**System prompt:**

> You are a carbon credit methodology expert. Given a project description, determine why it cannot use existing approved methodologies. Be conservative: if an existing methodology could apply, say so. Output strict JSON with keys: `fits_existing_methodology` (bool), `matching_methodologies` (list of objects with `name`, `reason`), `gaps` (list of strings), and `recommendation` (string).

**User prompt:**

> Project: {name}\nSector: {sector}\nActivity: {activity_description}\nBoundaries: {boundaries}\nData sources: {data_sources}\nExisting methodologies: {methodology_list}

### Call 2: Draft methodology

Triggered only when gap analysis confirms no existing methodology fits.

**System prompt:**

> You are drafting a carbon credit methodology aligned with Verra VCS and Gold Standard requirements. Output strict JSON with the following top-level keys: `applicability_conditions`, `baseline_scenario`, `project_scenario`, `additionality_approach`, `quantification_approach`, `leakage_assessment`, `monitoring_plan`, `uncertainty_approach`, `safeguards`, `co_benefits`, `registry_alignment_notes`. Each value should be a detailed paragraph or list. Additionally output `quantification_scaffold` with keys `equations` (list of LaTeX-like strings), `parameters` (list of objects with name, description, unit, data_source, uncertainty), and `monitoring_frequency`.

The structured output is parsed, stored in `methodology_json` and `quantification_scaffold_json`, and rendered in the frontend.

## Frontend Design

### Route

`/methodology-designer` (new top-level route added to `DashboardShell`).

### Wizard steps

1. **Project context** — select linked project or enter free-form context; sector, activity description, geographic scope.
2. **Boundaries & data** — system boundaries, GHG sources/sinks, available data sources and frequency.
3. **Gap analysis** — run AI comparison; display matching methodologies and gaps.
4. **Draft methodology** — generate and render structured sections; allow inline editing of JSON fields.
5. **Quantification scaffold** — review equations, parameters, monitoring plan.
6. **Review & export** — status actions and export to Markdown.

### Components

- `MethodologyWizard` — step container.
- `GapAnalysisPanel` — displays matches/gaps/recommendation.
- `MethodologySectionEditor` — renders/editable structured methodology.
- `QuantificationScaffoldViewer` — equations and parameters table.

## Review Workflow

```
draft → under_review → approved
                ↘ rejected
                ↘ revision_requested → draft
```

Status transitions are enforced in the service layer. Each transition writes an `AuditLogger` event with `action_type=methodology_updated` and the new status.

## Calculation Engine Integration

The `quantification_scaffold_json` follows a schema the calculation engine can consume:

```json
{
  "equations": ["ER_y = BE_y - PE_y - L_y"],
  "parameters": [
    {"name": "BE_y", "description": "Baseline emissions", "unit": "tCO2e/yr", "data_source": "historical_data", "uncertainty": 0.10}
  ],
  "monitoring_frequency": "annual",
  "calculation_type": "custom_methodology"
}
```

A future iteration can auto-create a `CalculationRun` from the scaffold. For the first version, a button **“Create calculation from scaffold”** copies the scaffold into a new calculation run payload.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| AI produces incorrect or over-crediting quantification | Always label output as draft; require operator/admin approval; include conservative default uncertainty. |
| AI hallucinates registry requirements | Prompt explicitly cites Verra/Gold Standard components; output includes `registry_alignment_notes`. |
| Feature used when existing methodology fits | Gap analysis call is conservative and must explicitly state if an approved methodology applies. |
| LLM unavailable | Return structured error; allow manual drafting with the same schema. |
| Data model drift | Keep `methodology_json` and `quantification_scaffold_json` as JSONB so the schema can evolve. |

## Success Metrics

- A user can complete the wizard and receive a structured gap analysis in under 60 seconds.
- Generated drafts include all 8 required methodology sections in ≥95% of cases.
- Review workflow status transitions are auditable.
- Approved drafts can be exported in a format usable for Verra MIN/Concept Note submission.

## Future Enhancements

- Vector-store RAG against Verra/Gold Standard methodology documents for more precise gap analysis.
- Auto-generation of quantification spreadsheets (Excel/CSV).
- Public-comment and independent-expert review stages mapped to Verra MDRP.
- Side-by-side diff when revisions are requested.
