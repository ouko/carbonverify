# AI Methodology Designer

CarbonVerify's **AI Methodology Designer** helps project developers, validators, and VVBs create registry-aligned draft methodologies for carbon projects that do not cleanly fit existing Verra or Gold Standard methodologies.

It is designed as a **human-in-the-loop** system: the AI accelerates analysis and drafting, but every draft must be reviewed and approved by a qualified operator or VVB before it can be used in a real project.

---

## Why this matters

Most carbon projects today use well-known methodologies such as TPDDTEC v4, VM0050, VMR0006, or AMS-II.G. But novel activities — for example:

- Blue carbon combined with community-managed no-take zones
- Regenerative agriculture with biochar amendments
- Distributed renewable microgrids with dynamic load balancing
- Plastic-to-fuel with tracked end-of-life emissions

— may fall outside the boundaries of any existing approved methodology. The traditional path is to hire consultants to write a bespoke methodology from scratch, which can take months and cost hundreds of thousands of dollars. The AI Methodology Designer reduces that to a structured, auditable workflow that produces a first draft in minutes.

---

## Workflow

| Step | UI | Backend endpoint | Purpose |
|------|----|------------------|---------|
| **1. Capture context** | Wizard form | `POST /methodology-generator/` | Store project name, sector, activity description, boundaries, and data sources |
| **2. Gap analysis** | Gap analysis panel | `POST /{id}/analyze` | Compare the activity against the existing methodology library and identify what is missing |
| **3. Draft generation** | Methodology draft viewer | `POST /{id}/generate` | Produce a registry-style draft: applicability, baseline, project boundary, leakage, monitoring plan, etc. |
| **4. Quantification scaffold** | Parameters / equations table | Included in step 3 | Define equations, parameters, data sources, uncertainty, and monitoring frequency |
| **5. Human review** | Status buttons | `PATCH /{id}/status` | Operator/VVB submits, approves, rejects, or requests revision; all changes are audit-logged |
| **6. Export** | Markdown download | `POST /{id}/export` | Download the approved draft as Markdown for further editing |

---

## Gap analysis output

The gap analysis endpoint returns a structured JSON object with the following fields:

```json
{
  "fits_existing_methodology": false,
  "matching_methodologies": [
    {"name": "VM0050", "reason": "Similar sector but different activity boundary"}
  ],
  "gaps": [
    "No approved baseline for the specific feedstock mix",
    "Leakage from displaced fuel use is not covered",
    "Monitoring parameter for digestate fate is missing"
  ],
  "recommendation": "Develop a new methodology combining IPCC Tier 2 factors with project-specific MRV."
}
```

If `fits_existing_methodology` is `true`, the system **blocks** draft generation to avoid creating a redundant or conflicting methodology.

---

## Draft methodology structure

A generated methodology contains registry-style sections such as:

- **Applicability conditions** — where the methodology can be used
- **Baseline scenario** — how baseline emissions are determined
- **Project boundary** — physical and temporal scope
- **Leakage assessment** — indirect emissions outside the boundary
- **Monitoring plan** — parameters, frequency, and data sources
- **Quantification approach** — equations and default factors

The quantification scaffold is stored separately so calculation engineers can map it directly to the CarbonVerify calculation engine.

---

## Configuration

The generator uses the Kimi API for live AI generation. Set the key in your environment:

```bash
KIMI_API_KEY=your_key_here
```

If `KIMI_API_KEY` is not set, the service returns a structured placeholder response so the UI and API can still be tested end-to-end. This is useful for local development and CI, but a production deployment must configure a real key.

---

## Permissions

| Action | Requirement |
|--------|-------------|
| Create / list / view / analyze / generate / export | Authenticated user (`get_current_user`) |
| Update review status | Operator or admin (`require_operator`) |

Status transitions are enforced by the backend:

- `draft` → `under_review`
- `under_review` → `approved`, `rejected`, or `revision_requested`
- `revision_requested` → `draft`

Rejections and revision requests require a `rejection_reason`.

---

## Database

The feature adds one table via Alembic migration `96ec14ae4fd3_add_generated_methodologies.py`:

- `generated_methodologies` — stores project context, gap analysis, methodology draft, quantification scaffold, status, and review metadata. JSON fields are stored as JSONB.

---

## Testing

Backend tests cover the full lifecycle:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_methodology_generator.py -v
```

Tests verify:

- Creating a generated methodology
- Running gap analysis
- Generating a draft and scaffold
- Blocking generation when the project fits an existing methodology
- Status transitions and rejection reason validation
- Markdown export

---

## Integration with the rest of CarbonVerify

- A generated methodology can be linked to a real project via `project_id`.
- The review workflow uses the same `audit_logs` table as other modules.
- The Markdown export can be uploaded to the document store or attached to a VVB submission.
- Future work: convert an approved generated methodology into a native calculation template.
