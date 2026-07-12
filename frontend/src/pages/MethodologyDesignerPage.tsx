import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { WizardStepper } from '../components/methodology-generator/WizardStepper'
import { GapAnalysisPanel } from '../components/methodology-generator/GapAnalysisPanel'
import { MethodologyDraftViewer } from '../components/methodology-generator/MethodologyDraftViewer'
import { QuantificationScaffoldViewer } from '../components/methodology-generator/QuantificationScaffoldViewer'
import {
  useCreateGeneratedMethodology,
  useGeneratedMethodology,
  useAnalyzeGap,
  useGenerateMethodology,
  useUpdateMethodologyStatus,
} from '../hooks/useMethodologyGenerator'

const STEPS = ['Context', 'Boundaries', 'Gap Analysis', 'Draft', 'Scaffold', 'Review']

export default function MethodologyDesignerPage() {
  const { id } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    project_id: '',
    name: '',
    sector: '',
    activity_description: '',
    boundaries: {},
    data_sources: [] as Array<Record<string, unknown>>,
  })

  const create = useCreateGeneratedMethodology()
  const { data: gm } = useGeneratedMethodology(id || '')
  const analyze = useAnalyzeGap()
  const generate = useGenerateMethodology()
  const updateStatus = useUpdateMethodologyStatus()

  const handleCreate = async () => {
    const created = await create.mutateAsync(form)
    navigate(`/methodology-designer/${created.id}`)
    setStep(2)
  }

  const handleAnalyze = async () => {
    if (id) await analyze.mutateAsync(id)
    setStep(3)
  }

  const handleGenerate = async () => {
    if (id) await generate.mutateAsync(id)
    setStep(4)
  }

  const handleStatus = (status: typeof gm.status) => {
    if (id) updateStatus.mutate({ id, payload: { status } })
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">AI Methodology Designer</h1>
      <p className="text-gray-600 mb-6">Generate registry-aligned draft methodologies for unique projects.</p>
      <WizardStepper current={step} steps={STEPS} />

      {step === 0 && (
        <div className="space-y-4">
          <input
            className="w-full border rounded p-2"
            placeholder="Methodology name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="w-full border rounded p-2"
            placeholder="Sector (e.g. Blue Carbon)"
            value={form.sector}
            onChange={(e) => setForm({ ...form, sector: e.target.value })}
          />
          <input
            className="w-full border rounded p-2"
            placeholder="Linked project ID (optional)"
            value={form.project_id}
            onChange={(e) => setForm({ ...form, project_id: e.target.value })}
          />
          <textarea
            className="w-full border rounded p-2"
            rows={4}
            placeholder="Describe the project activity..."
            value={form.activity_description}
            onChange={(e) => setForm({ ...form, activity_description: e.target.value })}
          />
          <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={() => setStep(1)}>
            Next
          </button>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <p className="text-gray-600">Define boundaries and data sources (simplified for this version).</p>
          <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={handleCreate}>
            Save & Analyze Gap
          </button>
        </div>
      )}

      {step === 2 && gm && (
        <div className="space-y-4">
          <GapAnalysisPanel gm={gm} />
          <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={handleAnalyze}>
            Generate Draft Methodology
          </button>
        </div>
      )}

      {step === 3 && gm && (
        <div className="space-y-4">
          <MethodologyDraftViewer gm={gm} />
          <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={handleGenerate}>
            Build Quantification Scaffold
          </button>
        </div>
      )}

      {step === 4 && gm && (
        <div className="space-y-4">
          <QuantificationScaffoldViewer gm={gm} />
          <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={() => setStep(5)}>
            Review & Export
          </button>
        </div>
      )}

      {step === 5 && gm && (
        <div className="space-y-4">
          <div className="flex space-x-2">
            <button className="bg-emerald-600 text-white px-4 py-2 rounded" onClick={() => handleStatus('under_review')}>
              Submit for Review
            </button>
            <button className="bg-blue-600 text-white px-4 py-2 rounded" onClick={() => handleStatus('approved')}>
              Approve
            </button>
            <button className="bg-red-600 text-white px-4 py-2 rounded" onClick={() => handleStatus('rejected')}>
              Reject
            </button>
          </div>
          <div className="text-sm text-gray-600">Current status: <strong>{gm.status}</strong></div>
        </div>
      )}
    </div>
  )
}
