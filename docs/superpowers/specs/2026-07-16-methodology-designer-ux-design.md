# Methodology Designer UX Improvements

## Background

CarbonVerify's AI Methodology Designer lets users create registry-aligned draft methodologies for projects that do not fit existing approved methodologies. The feature is already built end-to-end (backend service, FastAPI router, React wizard). Feedback from carbon consultants without deep methodology expertise shows that the current form is hard to fill out: labels are technical, fields have no examples, and there is no starting guidance.

## Goal

Make the methodology creation form easy for non-technical carbon consultants to complete accurately by:

1. Using plain-language labels and inline examples.
2. Adding sector-specific starting templates.
3. Providing a simple/advanced mode so users see only what they need.
4. Building the template infrastructure so the community can add more templates later.

## Non-Goals

- Replacing the existing 6-step wizard with a fully conversational Q&A flow.
- Adding admin UI for template CRUD in this iteration.
- Changing the AI gap-analysis or generation prompts.
- Modifying the `CreateGeneratedMethodologyPayload` shape sent to the backend.

## Target Users

Carbon consultants and project developers who understand the project but are not experts in Verra/Gold Standard methodology terminology.

## Design Overview

### UX Improvements

1. **Plain-language labels** with short helper text and placeholders.
2. **Inline validation** on blur and step navigation.
3. **Simple / advanced toggle** that hides technical optional fields by default.
4. **Template selector** at the top of Step 1 with 1–2 built-in templates.

### Backend Addition

A new `MethodologyTemplate` table stores sector defaults. Two seeded templates ship in v1:

- Cookstoves / Household Energy
- Blue Carbon / Coastal Ecosystems

Admins can add more templates directly in the database or via future seed/Alembic data migrations.

### Frontend Changes

- New reusable `FormField` component.
- New `MethodologyTemplateSelector` component.
- Updates to `MethodologyDesignerPage` for templates, simple/advanced mode, and inline validation.
- New `useMethodologyTemplates` hook.

## Detailed Design

### Plain-Language Labels

| Current label | New label | Helper text |
|---|---|---|
| Linked project | Project this methodology is for | Required. Choose an existing CarbonVerify project. |
| Methodology name | Methodology name | e.g., "Kenya Clean Cookstoves 2025" |
| Sector | Sector / project type | e.g., Cookstoves, Blue Carbon, Agroforestry |
| Activity description | What does the project do? | Describe the activity in plain English: what is measured, where it happens, and why existing methodologies don't fit. |
| Geographic scope | Where does the project operate? | e.g., Kwale County, Kenya |
| Temporal scope | What time period does it cover? | e.g., 2025-01-01 to 2034-12-31 |
| Physical boundary | What is included physically? | e.g., project-installation sites and supply chain |
| GHG sources included | Greenhouse gases covered (optional) | e.g., CO₂ and CH₄ from avoided biomass fuel combustion |
| Source type | Data source type | e.g., satellite imagery, household survey, IoT sensor |
| Frequency | How often is data collected? | e.g., monthly, annual, once per monitoring period |
| Provider / quality assurance notes | Data provider / QA notes (optional) | e.g., third-party enumerator, 10% spot checks |

### Simple / Advanced Mode

- Default to **Simple mode**.
- Hidden advanced fields:
  - `boundaries.ghg_sources_included`
  - `data_sources[].provider_quality`
- Hidden values remain in form state and are still submitted.
- Toggle is a switch at the top of Step 1 and Step 2.

### Template Selector

- Displayed as a card grid or dropdown on Step 1.
- Each card shows: template name, sector, one-line description.
- Selecting a template pre-fills:
  - `sector`
  - `boundaries` (all fields)
  - `data_sources` (one default source)
- Users can edit everything after applying a template.
- If the user has already entered data, show a confirmation dialog before overwriting.

## Backend Design

### New Model

```python
class MethodologyTemplate(Base):
    __tablename__ = "methodology_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    defaults_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

`defaults_json` schema:

```json
{
  "boundaries": {
    "geographic_scope": "string",
    "temporal_scope": "string",
    "physical_boundary": "string",
    "ghg_sources_included": "string"
  },
  "data_sources": [
    {
      "source_type": "string",
      "description": "string",
      "frequency": "string",
      "provider_quality": "string"
    }
  ]
}
```

### Service Layer

A small `MethodologyTemplateService` handles safe reads:

```python
class MethodologyTemplateService:
    async def list_active(self, db: AsyncSession) -> list[MethodologyTemplate]:
        result = await db.execute(
            select(MethodologyTemplate).where(MethodologyTemplate.is_active.is_(True))
        )
        return result.scalars().all()

    async def get(self, db: AsyncSession, template_id: uuid.UUID) -> MethodologyTemplate | None:
        result = await db.execute(
            select(MethodologyTemplate).where(
                MethodologyTemplate.id == template_id,
                MethodologyTemplate.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    def defaults_to_form(self, template: MethodologyTemplate) -> dict:
        """Return a safe, validated defaults dict for the frontend form."""
        raw = template.defaults_json or {}
        boundaries = raw.get("boundaries", {})
        data_sources = raw.get("data_sources", [])
        if not isinstance(data_sources, list):
            data_sources = []
        return {
            "sector": template.sector,
            "boundaries": {
                "geographic_scope": str(boundaries.get("geographic_scope", "")),
                "temporal_scope": str(boundaries.get("temporal_scope", "")),
                "physical_boundary": str(boundaries.get("physical_boundary", "")),
                "ghg_sources_included": str(boundaries.get("ghg_sources_included", "")),
            },
            "data_sources": [
                {
                    "source_type": str(ds.get("source_type", "")),
                    "description": str(ds.get("description", "")),
                    "frequency": str(ds.get("frequency", "")),
                    "provider_quality": str(ds.get("provider_quality", "")),
                }
                for ds in data_sources
                if isinstance(ds, dict)
            ],
        }
```

### API Endpoints

- `GET /methodology-templates/` — list active templates.
- `GET /methodology-templates/{id}` — get a single template.

No mutating endpoints in v1.

### Seeded Templates

Two templates are seeded via `scripts/seed_demo_data.py` (or an Alembic data migration):

1. **Cookstoves / Household Energy**
2. **Blue Carbon / Coastal Ecosystems**

## Frontend Design

### New Types

```typescript
export interface MethodologyTemplate {
  id: string
  name: string
  sector: string
  description?: string
  is_active: boolean
  defaults: {
    boundaries: BoundariesForm
    data_sources: DataSourceForm[]
  }
  created_by?: string
  created_at: string
  updated_at: string
}
```

### New Components

- `MethodologyTemplateSelector` — template picker on Step 1.
- `FormField` — reusable labeled input with helper text and error.
- `SimpleModeToggle` — switch to show/hide advanced fields.

### Modified Components

- `MethodologyDesignerPage`
  - Add `showAdvancedFields` state.
  - Add `applyTemplate` helper with overwrite confirmation.
  - Replace bare inputs with `FormField` wrappers.
  - Add per-field validation and inline errors.
- `WizardStepper` — no structural change.

### New Hook

- `useMethodologyTemplates()` — TanStack Query hook for `GET /methodology-templates/`.

## Data Flow

1. Page loads projects, templates, and existing methodology (if editing).
2. User selects a template; defaults are merged into form state.
3. User toggles simple/advanced mode; hidden fields remain in state.
4. Validation runs on blur and on step navigation.
5. `handleCreate` submits the same payload shape as today.

## Error Handling

- Template API failure: log warning, fall back to blank form.
- Malformed template JSON: service returns safe empty defaults.
- Overwrite on template change: confirmation dialog.
- Validation errors: inline field errors plus existing top-level banner for server errors.

## Testing Plan

### Backend

- Migration up/down succeeds.
- `MethodologyTemplateService` returns only active templates.
- Malformed `defaults_json` falls back safely.
- `GET /methodology-templates/` returns 200 with expected templates.
- Demo seed includes the two built-in templates.

### Frontend

- `MethodologyTemplateSelector` pre-fills form state.
- `SimpleModeToggle` hides/shows advanced fields.
- `FormField` renders label, helper, placeholder, and error.
- `npx tsc --noEmit` passes.
- `npm run lint` introduces no new errors.
- Manual QA verifies light and dark mode contrast.

### Manual End-to-End

- Create a methodology from the Cookstoves template, edit a field, run gap analysis.
- Verify switching templates warns before overwriting.
- Verify hidden advanced fields are still submitted.

## Success Metrics

- A carbon consultant can complete Step 1 and Step 2 without guessing what any field means.
- Time to create a methodology record from a template is under 2 minutes.
- No regression in existing methodology generator functionality.

## Future Enhancements

- Admin UI for creating/editing templates.
- More built-in templates (Renewable Energy, Agroforestry, etc.).
- AI-powered template suggestion based on project description.
