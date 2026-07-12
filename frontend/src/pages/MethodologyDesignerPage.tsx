import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { GeneratedMethodology, Project } from '../types'
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
import { useProjects } from '../hooks/useProjects'
import { api } from '../services/api'
import { Loader2, AlertCircle, CheckCircle2, Info, Plus, Trash2 } from 'lucide-react'

const STEPS = ['Context', 'Boundaries', 'Gap Analysis', 'Draft', 'Scaffold', 'Review']

interface BoundariesForm {
  geographic_scope: string
  temporal_scope: string
  physical_boundary: string
  ghg_sources_included: string
}

interface DataSourceForm {
  source_type: string
  description: string
  frequency: string
  provider_quality: string
}

interface PageForm {
  project_id: string
  name: string
  sector: string
  activity_description: string
  boundaries: BoundariesForm
  data_sources: DataSourceForm[]
}

const INITIAL_BOUNDARIES: BoundariesForm = {
  geographic_scope: '',
  temporal_scope: '',
  physical_boundary: '',
  ghg_sources_included: '',
}

const INITIAL_DATA_SOURCE: DataSourceForm = {
  source_type: '',
  description: '',
  frequency: '',
  provider_quality: '',
}

function getErrorMessage(err: unknown): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string }
    return axiosErr.response?.data?.detail || axiosErr.message || 'An unexpected error occurred.'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred.'
}

function StepCard({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-4">
      <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900 rounded p-4 flex items-start space-x-3">
        <Info className="w-5 h-5 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
        <div>
          <h3 className="font-semibold text-emerald-900 dark:text-emerald-100">{title}</h3>
          <p className="text-sm text-emerald-800 dark:text-emerald-200">{description}</p>
        </div>
      </div>
      {children}
    </div>
  )
}

function Alert({ type, message }: { type: 'error' | 'success'; message: string }) {
  const isError = type === 'error'
  const Icon = isError ? AlertCircle : CheckCircle2
  return (
    <div
      className={`rounded p-3 flex items-start space-x-2 text-sm ${
        isError
          ? 'bg-red-50 text-red-800 border border-red-100 dark:bg-red-950/30 dark:text-red-200 dark:border-red-900'
          : 'bg-green-50 text-green-800 border border-green-100 dark:bg-green-950/30 dark:text-green-200 dark:border-green-900'
      }`}
    >
      <Icon className="w-4 h-4 mt-0.5 flex-shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export default function MethodologyDesignerPage() {
  const { id } = useParams<{ id?: string }>()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<PageForm>({
    project_id: '',
    name: '',
    sector: '',
    activity_description: '',
    boundaries: { ...INITIAL_BOUNDARIES },
    data_sources: [{ ...INITIAL_DATA_SOURCE }],
  })
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')

  const create = useCreateGeneratedMethodology()
  const {
    data: gm,
    isLoading: gmLoading,
    error: gmError,
  } = useGeneratedMethodology(id || '')
  const analyze = useAnalyzeGap()
  const generate = useGenerateMethodology()
  const updateStatus = useUpdateMethodologyStatus()
  const { data: projects, isLoading: projectsLoading } = useProjects()

  const anyLoading =
    create.isPending || analyze.isPending || generate.isPending || updateStatus.isPending

  const setField = <K extends keyof PageForm>(key: K, value: PageForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const setBoundary = (key: keyof BoundariesForm, value: string) => {
    setForm((prev) => ({ ...prev, boundaries: { ...prev.boundaries, [key]: value } }))
  }

  const setDataSource = (idx: number, key: keyof DataSourceForm, value: string) => {
    setForm((prev) => {
      const next = [...prev.data_sources]
      next[idx] = { ...next[idx], [key]: value }
      return { ...prev, data_sources: next }
    })
  }

  const addDataSource = () => {
    setForm((prev) => ({ ...prev, data_sources: [...prev.data_sources, { ...INITIAL_DATA_SOURCE }] }))
  }

  const removeDataSource = (idx: number) => {
    setForm((prev) => ({
      ...prev,
      data_sources: prev.data_sources.filter((_, i) => i !== idx),
    }))
  }

  const validateContext = (): string | null => {
    if (!form.project_id) return 'Please select a linked project.'
    if (!form.name.trim()) return 'Methodology name is required.'
    if (!form.sector.trim()) return 'Sector is required.'
    if (form.activity_description.trim().length < 10)
      return 'Activity description must be at least 10 characters.'
    return null
  }

  const validateBoundaries = (): string | null => {
    if (!form.boundaries.geographic_scope.trim()) return 'Geographic scope is required.'
    if (!form.boundaries.temporal_scope.trim()) return 'Temporal scope is required.'
    if (!form.boundaries.physical_boundary.trim()) return 'Physical boundary is required.'
    if (form.data_sources.length === 0) return 'Add at least one data source.'
    for (let i = 0; i < form.data_sources.length; i++) {
      const ds = form.data_sources[i]
      if (!ds.source_type.trim() || !ds.description.trim()) {
        return `Data source #${i + 1} needs a type and description.`
      }
    }
    return null
  }

  const toPayload = () => ({
    project_id: form.project_id,
    name: form.name.trim(),
    sector: form.sector.trim(),
    activity_description: form.activity_description.trim(),
    boundaries: {
      geographic_scope: form.boundaries.geographic_scope.trim(),
      temporal_scope: form.boundaries.temporal_scope.trim(),
      physical_boundary: form.boundaries.physical_boundary.trim(),
      ghg_sources_included: form.boundaries.ghg_sources_included.trim(),
    },
    data_sources: form.data_sources
      .filter((ds) => ds.source_type.trim() || ds.description.trim())
      .map((ds) => ({
        source_type: ds.source_type.trim(),
        description: ds.description.trim(),
        frequency: ds.frequency.trim(),
        provider_quality: ds.provider_quality.trim(),
      })),
  })

  const handleCreate = async () => {
    setError(null)
    setSuccess(null)
    const contextErr = validateContext()
    if (contextErr) {
      setError(contextErr)
      return
    }
    const boundaryErr = validateBoundaries()
    if (boundaryErr) {
      setError(boundaryErr)
      return
    }
    try {
      const created = await create.mutateAsync(toPayload())
      setSuccess('Methodology record created.')
      navigate(`/methodology-designer/${created.id}`)
      setStep(2)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const handleAnalyze = async () => {
    if (!id) return
    setError(null)
    setSuccess(null)
    try {
      await analyze.mutateAsync(id)
      setSuccess('Gap analysis complete.')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const handleGenerate = async () => {
    if (!id) return
    setError(null)
    setSuccess(null)
    try {
      await generate.mutateAsync(id)
      setSuccess('Draft methodology and quantification scaffold generated.')
      setStep(3)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const handleStatus = async (status: GeneratedMethodology['status']) => {
    if (!id) return
    setError(null)
    setSuccess(null)
    const needsReason = status === 'rejected' || status === 'revision_requested'
    if (needsReason && !rejectionReason.trim()) {
      setError('Please provide a rejection / revision reason.')
      return
    }
    try {
      await updateStatus.mutateAsync({
        id,
        payload: { status, rejection_reason: needsReason ? rejectionReason.trim() : undefined },
      })
      setSuccess(`Status updated to ${status.replace(/_/g, ' ')}.`)
      setRejectionReason('')
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const selectedProject = projects?.find((p) => p.id === form.project_id)

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">AI Methodology Designer</h1>
      <p className="text-gray-600 dark:text-gray-300 mb-6">
        Generate registry-aligned draft methodologies for projects that do not fit existing
        methodologies.
      </p>
      <WizardStepper current={step} steps={STEPS} />

      {error && <Alert type="error" message={error} />}
      {success && <Alert type="success" message={success} />}
      {gmError && !error && (
        <Alert type="error" message={getErrorMessage(gmError)} />
      )}

      <div className="mt-6">
        {step === 0 && (
          <StepCard
            title="Project context"
            description="Choose the project this methodology belongs to, then describe the activity and sector so the AI can compare it against existing methodologies."
          >
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Linked project *</label>
                {projectsLoading ? (
                  <div className="flex items-center space-x-2 text-gray-500">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Loading projects...</span>
                  </div>
                ) : (
                  <>
                    <select
                      className="w-full border rounded p-2 bg-white dark:bg-surface-900"
                      value={form.project_id}
                      onChange={(e) => setField('project_id', e.target.value)}
                    >
                      <option value="">Select an existing project</option>
                      {projects?.map((project: Project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                    {(!projects || projects.length === 0) && (
                      <p className="text-sm text-amber-600 mt-1">
                        No projects found. Create a project first from the Projects page.
                      </p>
                    )}
                  </>
                )}
              </div>

              <input
                className="w-full border rounded p-2"
                placeholder="Methodology name *"
                value={form.name}
                onChange={(e) => setField('name', e.target.value)}
              />
              <input
                className="w-full border rounded p-2"
                placeholder="Sector (e.g. Blue Carbon, Cookstoves) *"
                value={form.sector}
                onChange={(e) => setField('sector', e.target.value)}
              />
              <textarea
                className="w-full border rounded p-2"
                rows={4}
                placeholder="Describe the project activity in detail (at least 10 characters) *"
                value={form.activity_description}
                onChange={(e) => setField('activity_description', e.target.value)}
              />
              <p className="text-xs text-gray-500">
                Tip: include what is being measured, where it happens, and why existing methodologies
                may not apply.
              </p>
              <button
                className="bg-emerald-600 text-white px-4 py-2 rounded inline-flex items-center space-x-2 disabled:opacity-50"
                onClick={() => {
                  const err = validateContext()
                  if (err) {
                    setError(err)
                    return
                  }
                  setError(null)
                  setStep(1)
                }}
              >
                <span>Next: Boundaries & Data Sources</span>
              </button>
            </div>
          </StepCard>
        )}

        {step === 1 && (
          <StepCard
            title="Boundaries & data sources"
            description="Define the system boundary and list the data sources the project will use. The AI uses these to assess gaps and build a quantification scaffold."
          >
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Geographic scope *</label>
                  <input
                    className="w-full border rounded p-2"
                    placeholder="e.g. Kwale County, Kenya"
                    value={form.boundaries.geographic_scope}
                    onChange={(e) => setBoundary('geographic_scope', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Temporal scope *</label>
                  <input
                    className="w-full border rounded p-2"
                    placeholder="e.g. 2025-01-01 to 2034-12-31"
                    value={form.boundaries.temporal_scope}
                    onChange={(e) => setBoundary('temporal_scope', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Physical boundary *</label>
                  <input
                    className="w-full border rounded p-2"
                    placeholder="e.g. project-installation sites and supply chain"
                    value={form.boundaries.physical_boundary}
                    onChange={(e) => setBoundary('physical_boundary', e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">GHG sources included</label>
                  <input
                    className="w-full border rounded p-2"
                    placeholder="e.g. CO2, CH4 from avoided fuel combustion"
                    value={form.boundaries.ghg_sources_included}
                    onChange={(e) => setBoundary('ghg_sources_included', e.target.value)}
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium">Data sources *</label>
                  <button
                    className="text-sm text-emerald-600 hover:text-emerald-700 inline-flex items-center space-x-1"
                    onClick={addDataSource}
                    disabled={anyLoading}
                  >
                    <Plus className="w-4 h-4" />
                    <span>Add source</span>
                  </button>
                </div>
                <div className="space-y-3">
                  {form.data_sources.map((ds, idx) => (
                    <div
                      key={idx}
                      className="border rounded p-3 bg-gray-50 dark:bg-surface-900/50"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                          className="w-full border rounded p-2 bg-white dark:bg-surface-900"
                          placeholder="Source type (e.g. satellite, IoT, survey) *"
                          value={ds.source_type}
                          onChange={(e) => setDataSource(idx, 'source_type', e.target.value)}
                        />
                        <input
                          className="w-full border rounded p-2 bg-white dark:bg-surface-900"
                          placeholder="Frequency (e.g. monthly, annual)"
                          value={ds.frequency}
                          onChange={(e) => setDataSource(idx, 'frequency', e.target.value)}
                        />
                        <input
                          className="w-full md:col-span-2 border rounded p-2 bg-white dark:bg-surface-900"
                          placeholder="Description of what the source measures *"
                          value={ds.description}
                          onChange={(e) => setDataSource(idx, 'description', e.target.value)}
                        />
                        <input
                          className="w-full md:col-span-2 border rounded p-2 bg-white dark:bg-surface-900"
                          placeholder="Provider / quality assurance notes"
                          value={ds.provider_quality}
                          onChange={(e) => setDataSource(idx, 'provider_quality', e.target.value)}
                        />
                      </div>
                      {form.data_sources.length > 1 && (
                        <button
                          className="mt-2 text-sm text-red-600 hover:text-red-700 inline-flex items-center space-x-1"
                          onClick={() => removeDataSource(idx)}
                          disabled={anyLoading}
                        >
                          <Trash2 className="w-4 h-4" />
                          <span>Remove</span>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  className="px-4 py-2 rounded border"
                  onClick={() => setStep(0)}
                  disabled={anyLoading}
                >
                  Back
                </button>
                <button
                  className="bg-emerald-600 text-white px-4 py-2 rounded inline-flex items-center space-x-2 disabled:opacity-50"
                  onClick={handleCreate}
                  disabled={anyLoading}
                >
                  {create.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  <span>Save & Analyze Gap</span>
                </button>
              </div>
            </div>
          </StepCard>
        )}

        {step === 2 && (
          <StepCard
            title="Gap analysis"
            description="Compare the project against existing methodologies. If a good match exists, custom draft generation is blocked."
          >
            {gmLoading ? (
              <div className="flex items-center space-x-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading methodology record...</span>
              </div>
            ) : !gm ? (
              <p className="text-gray-500">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                {selectedProject && (
                  <p className="text-sm text-gray-600">
                    Linked project: <strong>{selectedProject.name}</strong>
                  </p>
                )}
                <GapAnalysisPanel gm={gm} />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    className="px-4 py-2 rounded border"
                    onClick={() => setStep(1)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="bg-emerald-600 text-white px-4 py-2 rounded inline-flex items-center space-x-2 disabled:opacity-50"
                    onClick={handleAnalyze}
                    disabled={anyLoading}
                  >
                    {analyze.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>{gm.gap_analysis ? 'Regenerate Gap Analysis' : 'Run Gap Analysis'}</span>
                  </button>
                  {gm.gap_analysis && (
                    <button
                      className="bg-blue-600 text-white px-4 py-2 rounded inline-flex items-center space-x-2 disabled:opacity-50"
                      onClick={handleGenerate}
                      disabled={anyLoading || gm.gap_analysis.fits_existing_methodology === true}
                    >
                      {generate.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                      <span>Generate Draft Methodology</span>
                    </button>
                  )}
                </div>
                {gm.gap_analysis?.fits_existing_methodology === true && (
                  <p className="text-sm text-amber-700 bg-amber-50 p-3 rounded border border-amber-100">
                    The AI believes this activity may fit an existing methodology. Draft generation
                    is disabled to avoid creating a redundant methodology.
                  </p>
                )}
              </div>
            )}
          </StepCard>
        )}

        {step === 3 && (
          <StepCard
            title="Draft methodology"
            description="Review the AI-generated methodology sections. If they look correct, proceed to the quantification scaffold."
          >
            {gmLoading ? (
              <div className="flex items-center space-x-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-gray-500">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <MethodologyDraftViewer gm={gm} />
                <div className="flex items-center space-x-3">
                  <button
                    className="px-4 py-2 rounded border"
                    onClick={() => setStep(2)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50"
                    onClick={() => setStep(4)}
                    disabled={anyLoading}
                  >
                    Next: Quantification Scaffold
                  </button>
                </div>
              </div>
            )}
          </StepCard>
        )}

        {step === 4 && (
          <StepCard
            title="Quantification scaffold"
            description="Review equations, parameters, and monitoring frequency. This scaffold is what the calculation engine will eventually execute."
          >
            {gmLoading ? (
              <div className="flex items-center space-x-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-gray-500">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <QuantificationScaffoldViewer gm={gm} />
                <div className="flex items-center space-x-3">
                  <button
                    className="px-4 py-2 rounded border"
                    onClick={() => setStep(3)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50"
                    onClick={() => setStep(5)}
                    disabled={anyLoading}
                  >
                    Review & Export
                  </button>
                </div>
              </div>
            )}
          </StepCard>
        )}

        {step === 5 && (
          <StepCard
            title="Review & export"
            description="Submit the draft for review, approve it, or request revisions. Rejections and revision requests require a reason."
          >
            {gmLoading ? (
              <div className="flex items-center space-x-2 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-gray-500">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <div className="text-sm text-gray-600">
                  Current status: <strong className="uppercase">{gm.status.replace(/_/g, ' ')}</strong>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Rejection / revision reason
                  </label>
                  <textarea
                    className="w-full border rounded p-2"
                    rows={3}
                    placeholder="Required when rejecting or requesting revisions"
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    className="bg-emerald-600 text-white px-4 py-2 rounded inline-flex items-center space-x-2 disabled:opacity-50"
                    onClick={() => handleStatus('under_review')}
                    disabled={anyLoading || gm.status !== 'draft'}
                  >
                    {updateStatus.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>Submit for Review</span>
                  </button>
                  <button
                    className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
                    onClick={() => handleStatus('approved')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Approve
                  </button>
                  <button
                    className="bg-red-600 text-white px-4 py-2 rounded disabled:opacity-50"
                    onClick={() => handleStatus('rejected')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Reject
                  </button>
                  <button
                    className="bg-amber-600 text-white px-4 py-2 rounded disabled:opacity-50"
                    onClick={() => handleStatus('revision_requested')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Request Revision
                  </button>
                </div>

                <div className="flex items-center space-x-3 pt-2">
                  <button
                    className="px-4 py-2 rounded border"
                    onClick={() => setStep(4)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  {gm.methodology && (
                    <button
                      className="px-4 py-2 rounded border border-emerald-600 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                      onClick={async () => {
                        if (!id) return
                        try {
                          const res = await api.post(`/methodology-generator/${id}/export`)
                          const data = res.data as { format: string; content: string }
                          const blob = new Blob([data.content], { type: 'text/markdown' })
                          const url = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = url
                          a.download = `${gm.name.replace(/\s+/g, '_')}_methodology.md`
                          a.click()
                          URL.revokeObjectURL(url)
                          setSuccess('Export downloaded.')
                        } catch (err) {
                          setError(getErrorMessage(err))
                        }
                      }}
                      disabled={anyLoading}
                    >
                      Export Markdown
                    </button>
                  )}
                </div>
              </div>
            )}
          </StepCard>
        )}
      </div>
    </div>
  )
}
