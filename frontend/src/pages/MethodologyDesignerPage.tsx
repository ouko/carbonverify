import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { BoundariesForm, DataSourceForm, GeneratedMethodology, MethodologyTemplate, Project } from '../types'
import { WizardStepper } from '../components/methodology-generator/WizardStepper'
import { GapAnalysisPanel } from '../components/methodology-generator/GapAnalysisPanel'
import { MethodologyDraftViewer } from '../components/methodology-generator/MethodologyDraftViewer'
import { QuantificationScaffoldViewer } from '../components/methodology-generator/QuantificationScaffoldViewer'
import { FormField } from '../components/methodology-generator/FormField'
import { MethodologyTemplateSelector } from '../components/methodology-generator/MethodologyTemplateSelector'
import { SimpleModeToggle } from '../components/methodology-generator/SimpleModeToggle'
import {
  useCreateGeneratedMethodology,
  useGeneratedMethodology,
  useAnalyzeGap,
  useGenerateMethodology,
  useUpdateMethodologyStatus,
  useMethodologyTemplates,
} from '../hooks/useMethodologyGenerator'
import { useProjects } from '../hooks/useProjects'
import { api } from '../services/api'
import { Loader2, AlertCircle, CheckCircle2, Info, Plus, Trash2 } from 'lucide-react'

const STEPS = ['Context', 'Boundaries', 'Gap Analysis', 'Draft', 'Scaffold', 'Review']

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
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const { data: templates, isLoading: templatesLoading } = useMethodologyTemplates()

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
    setFieldErrors((prev) => ({ ...prev, data_sources: '' }))
    setSelectedTemplateId(null)
  }

  const removeDataSource = (idx: number) => {
    setForm((prev) => ({
      ...prev,
      data_sources: prev.data_sources.filter((_, i) => i !== idx),
    }))
    setFieldErrors((prev) => {
      const next: Record<string, string> = {}
      Object.entries(prev).forEach(([key, value]) => {
        if (key === `data_source_${idx}`) return
        if (key.startsWith('data_source_')) {
          const sourceIdx = parseInt(key.replace('data_source_', ''), 10)
          if (sourceIdx > idx) {
            next[`data_source_${sourceIdx - 1}`] = value
          } else {
            next[key] = value
          }
        } else {
          next[key] = value
        }
      })
      next.data_sources = ''
      return next
    })
    setSelectedTemplateId(null)
  }

  const applyTemplate = (template: MethodologyTemplate) => {
    const defaults = template.defaults_json
    setSelectedTemplateId(template.id)
    setForm((prev) => ({
      ...prev,
      sector: template.sector,
      boundaries: {
        geographic_scope: defaults.boundaries?.geographic_scope ?? '',
        temporal_scope: defaults.boundaries?.temporal_scope ?? '',
        physical_boundary: defaults.boundaries?.physical_boundary ?? '',
        ghg_sources_included: defaults.boundaries?.ghg_sources_included ?? '',
      },
      data_sources:
        defaults.data_sources && defaults.data_sources.length > 0
          ? defaults.data_sources.map((ds) => ({
              source_type: ds.source_type ?? '',
              description: ds.description ?? '',
              frequency: ds.frequency ?? '',
              provider_quality: ds.provider_quality ?? '',
            }))
          : [{ ...INITIAL_DATA_SOURCE }],
    }))
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.sector
      delete next.geographic_scope
      delete next.temporal_scope
      delete next.physical_boundary
      delete next.data_sources
      Object.keys(next).forEach((key) => {
        if (key.startsWith('data_source_')) delete next[key]
      })
      return next
    })
  }

  const validateContext = (): string | null => {
    const errors: Record<string, string> = {}
    if (!form.project_id) errors.project_id = 'Please select a linked project.'
    if (!form.name.trim()) errors.name = 'Methodology name is required.'
    if (!form.sector.trim()) errors.sector = 'Sector is required.'
    if (form.activity_description.trim().length < 10)
      errors.activity_description = 'Activity description must be at least 10 characters.'
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.project_id
      delete next.name
      delete next.sector
      delete next.activity_description
      return { ...next, ...errors }
    })
    return Object.keys(errors).length > 0 ? 'Please fix the highlighted fields.' : null
  }

  const validateBoundaries = (): string | null => {
    const errors: Record<string, string> = {}
    if (!form.boundaries.geographic_scope.trim())
      errors.geographic_scope = 'Geographic scope is required.'
    if (!form.boundaries.temporal_scope.trim()) errors.temporal_scope = 'Temporal scope is required.'
    if (!form.boundaries.physical_boundary.trim())
      errors.physical_boundary = 'Physical boundary is required.'
    if (form.data_sources.length === 0) errors.data_sources = 'Add at least one data source.'
    for (let i = 0; i < form.data_sources.length; i++) {
      const ds = form.data_sources[i]
      if (!ds.source_type.trim() || !ds.description.trim()) {
        errors[`data_source_${i}`] = `Data source #${i + 1} needs a type and description.`
      }
    }
    setFieldErrors((prev) => {
      const next = { ...prev }
      delete next.geographic_scope
      delete next.temporal_scope
      delete next.physical_boundary
      delete next.data_sources
      Object.keys(next).forEach((key) => {
        if (key.startsWith('data_source_')) delete next[key]
      })
      return { ...next, ...errors }
    })
    return Object.keys(errors).length > 0 ? 'Please fix the highlighted fields.' : null
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
      <h1 className="page-title mb-2">AI Methodology Designer</h1>
      <p className="text-surface-600 dark:text-surface-400 mb-6">
        Generate registry-aligned draft methodologies for projects that do not fit existing
        methodologies.
      </p>
      <WizardStepper current={step} steps={STEPS} />

      {error && <Alert type="error" message={error} />}
      {success && <Alert type="success" message={success} />}
      {gmError && !error && <Alert type="error" message={getErrorMessage(gmError)} />}

      <div className="mt-6">
        {step === 0 && (
          <StepCard
            title="Project context"
            description="Choose the project this methodology belongs to, then describe the activity and sector so the AI can compare it against existing methodologies."
          >
            <div className="space-y-4">
              {templatesLoading ? (
                <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Loading templates...</span>
                </div>
              ) : templates && templates.length > 0 ? (
                <MethodologyTemplateSelector
                  templates={templates}
                  selectedId={selectedTemplateId ?? undefined}
                  onSelect={applyTemplate}
                />
              ) : null}

              <FormField
                label="Project this methodology is for *"
                htmlFor="project_id"
                error={fieldErrors.project_id}
              >
                {projectsLoading ? (
                  <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Loading projects...</span>
                  </div>
                ) : (
                  <>
                    <select
                      id="project_id"
                      className="input-modern"
                      value={form.project_id}
                      onChange={(e) => {
                        setField('project_id', e.target.value)
                        setFieldErrors((prev) => ({ ...prev, project_id: '' }))
                      }}
                    >
                      <option value="">Select an existing project</option>
                      {projects?.map((project: Project) => (
                        <option key={project.id} value={project.id}>
                          {project.name}
                        </option>
                      ))}
                    </select>
                    {(!projects || projects.length === 0) && (
                      <p className="text-sm text-amber-600 dark:text-amber-400 mt-1">
                        No projects found. Create a project first from the Projects page.
                      </p>
                    )}
                  </>
                )}
              </FormField>

              <FormField
                label="Methodology name *"
                htmlFor="name"
                helper="Choose a clear, descriptive name. Example: Improved Cookstoves Distribution Methodology v1.0"
                error={fieldErrors.name}
              >
                <input
                  id="name"
                  className="input-modern"
                  placeholder="e.g. Mangrove Restoration Methodology v1.0"
                  value={form.name}
                  onChange={(e) => {
                    setField('name', e.target.value)
                    setFieldErrors((prev) => ({ ...prev, name: '' }))
                  }}
                />
              </FormField>

              <FormField
                label="Sector / project type *"
                htmlFor="sector"
                helper="Pick the sector that best describes the project. Examples: Blue Carbon, Cookstoves, Forestry, Renewable Energy."
                error={fieldErrors.sector}
              >
                <input
                  id="sector"
                  className="input-modern"
                  placeholder="e.g. Blue Carbon, Cookstoves"
                  value={form.sector}
                  onChange={(e) => {
                    setField('sector', e.target.value)
                    setFieldErrors((prev) => ({ ...prev, sector: '' }))
                    setSelectedTemplateId(null)
                  }}
                />
              </FormField>

              <FormField
                label="Activity description *"
                htmlFor="activity_description"
                helper="Include what is being measured, where it happens, and why existing methodologies may not apply."
                error={fieldErrors.activity_description}
              >
                <textarea
                  id="activity_description"
                  className="input-modern"
                  rows={4}
                  placeholder="Describe the project activity in detail (at least 10 characters)"
                  value={form.activity_description}
                  onChange={(e) => {
                    setField('activity_description', e.target.value)
                    setFieldErrors((prev) => ({ ...prev, activity_description: '' }))
                  }}
                />
              </FormField>

              <button
                className="btn-primary"
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
              <div className="flex justify-end">
                <SimpleModeToggle showAdvanced={showAdvanced} onChange={setShowAdvanced} />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  label="Geographic scope *"
                  htmlFor="geographic_scope"
                  helper="Where will the project activity take place?"
                  error={fieldErrors.geographic_scope}
                >
                  <input
                    id="geographic_scope"
                    className="input-modern"
                    placeholder="e.g. Kwale County, Kenya"
                    value={form.boundaries.geographic_scope}
                    onChange={(e) => {
                      setBoundary('geographic_scope', e.target.value)
                      setFieldErrors((prev) => ({ ...prev, geographic_scope: '' }))
                      setSelectedTemplateId(null)
                    }}
                  />
                </FormField>

                <FormField
                  label="Temporal scope *"
                  htmlFor="temporal_scope"
                  helper="What time period will the methodology cover?"
                  error={fieldErrors.temporal_scope}
                >
                  <input
                    id="temporal_scope"
                    className="input-modern"
                    placeholder="e.g. 2025-01-01 to 2034-12-31"
                    value={form.boundaries.temporal_scope}
                    onChange={(e) => {
                      setBoundary('temporal_scope', e.target.value)
                      setFieldErrors((prev) => ({ ...prev, temporal_scope: '' }))
                      setSelectedTemplateId(null)
                    }}
                  />
                </FormField>

                <FormField
                  label="Physical boundary *"
                  htmlFor="physical_boundary"
                  helper="What physical assets, sites, or processes are included?"
                  error={fieldErrors.physical_boundary}
                >
                  <input
                    id="physical_boundary"
                    className="input-modern"
                    placeholder="e.g. project-installation sites and supply chain"
                    value={form.boundaries.physical_boundary}
                    onChange={(e) => {
                      setBoundary('physical_boundary', e.target.value)
                      setFieldErrors((prev) => ({ ...prev, physical_boundary: '' }))
                      setSelectedTemplateId(null)
                    }}
                  />
                </FormField>

                {showAdvanced && (
                  <FormField
                    label="Greenhouse gases covered (optional)"
                    htmlFor="ghg_sources_included"
                    helper="Which greenhouse gases and sources are explicitly included?"
                    advanced
                  >
                    <input
                      id="ghg_sources_included"
                      className="input-modern"
                      placeholder="e.g. CO2, CH4 from avoided fuel combustion"
                      value={form.boundaries.ghg_sources_included}
                      onChange={(e) => {
                        setBoundary('ghg_sources_included', e.target.value)
                        setFieldErrors((prev) => ({ ...prev, ghg_sources_included: '' }))
                        setSelectedTemplateId(null)
                      }}
                    />
                  </FormField>
                )}
              </div>

              <FormField label="Data sources *" error={fieldErrors.data_sources}>
                <div className="space-y-3">
                  {form.data_sources.map((ds, idx) => (
                    <div
                      key={idx}
                      className="border border-surface-200 dark:border-surface-700 rounded-xl p-3 bg-surface-50 dark:bg-surface-900/50"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <FormField
                          label="Source type *"
                          htmlFor={`source_type_${idx}`}
                          helper="e.g. satellite, IoT sensor, survey"
                          error={fieldErrors[`data_source_${idx}`]}
                        >
                          <input
                            id={`source_type_${idx}`}
                            className="input-modern"
                            placeholder="e.g. satellite, IoT, survey"
                            value={ds.source_type}
                            onChange={(e) => {
                              setDataSource(idx, 'source_type', e.target.value)
                              setFieldErrors((prev) => ({ ...prev, [`data_source_${idx}`]: '' }))
                              setSelectedTemplateId(null)
                            }}
                          />
                        </FormField>

                        <FormField
                          label="Frequency"
                          htmlFor={`frequency_${idx}`}
                          helper="How often is the data collected?"
                        >
                          <input
                            id={`frequency_${idx}`}
                            className="input-modern"
                            placeholder="e.g. monthly, annual"
                            value={ds.frequency}
                            onChange={(e) => {
                              setDataSource(idx, 'frequency', e.target.value)
                              setFieldErrors((prev) => ({ ...prev, [`data_source_${idx}`]: '' }))
                              setSelectedTemplateId(null)
                            }}
                          />
                        </FormField>

                        <div className="md:col-span-2">
                          <FormField
                            label="Description *"
                            htmlFor={`description_${idx}`}
                            helper="What does this source measure and how is it used?"
                            error={fieldErrors[`data_source_${idx}`]}
                          >
                            <input
                              id={`description_${idx}`}
                              className="w-full input-modern"
                              placeholder="Description of what the source measures"
                              value={ds.description}
                              onChange={(e) => {
                                setDataSource(idx, 'description', e.target.value)
                                setFieldErrors((prev) => ({ ...prev, [`data_source_${idx}`]: '' }))
                                setSelectedTemplateId(null)
                              }}
                            />
                          </FormField>
                        </div>

                        {showAdvanced && (
                          <div className="md:col-span-2">
                            <FormField
                              label="Provider / quality assurance"
                              htmlFor={`provider_quality_${idx}`}
                              helper="Who provides the data and how is quality assured?"
                              advanced
                            >
                              <input
                                id={`provider_quality_${idx}`}
                                className="w-full input-modern"
                                placeholder="Provider / quality assurance notes"
                                value={ds.provider_quality}
                                onChange={(e) => {
                                  setDataSource(idx, 'provider_quality', e.target.value)
                                  setFieldErrors((prev) => ({ ...prev, [`data_source_${idx}`]: '' }))
                                  setSelectedTemplateId(null)
                                }}
                              />
                            </FormField>
                          </div>
                        )}
                      </div>
                      {form.data_sources.length > 1 && (
                        <button
                          className="mt-2 text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 inline-flex items-center space-x-1"
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
                <button
                  className="mt-3 text-sm text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 dark:hover:text-emerald-300 inline-flex items-center space-x-1"
                  onClick={addDataSource}
                  disabled={anyLoading}
                >
                  <Plus className="w-4 h-4" />
                  <span>Add source</span>
                </button>
              </FormField>

              <div className="flex items-center space-x-3">
                <button className="btn-secondary" onClick={() => setStep(0)} disabled={anyLoading}>
                  Back
                </button>
                <button className="btn-primary" onClick={handleCreate} disabled={anyLoading}>
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
              <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading methodology record...</span>
              </div>
            ) : !gm ? (
              <p className="text-surface-500 dark:text-surface-400">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                {selectedProject && (
                  <p className="text-sm text-surface-700 dark:text-surface-300">
                    Linked project: <strong>{selectedProject.name}</strong>
                  </p>
                )}
                <GapAnalysisPanel gm={gm} />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    className="btn-secondary"
                    onClick={() => setStep(1)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="btn-primary"
                    onClick={handleAnalyze}
                    disabled={anyLoading}
                  >
                    {analyze.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>{gm.gap_analysis ? 'Regenerate Gap Analysis' : 'Run Gap Analysis'}</span>
                  </button>
                  {gm.gap_analysis && (
                    <button
                      className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-500 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                      onClick={handleGenerate}
                      disabled={anyLoading || gm.gap_analysis.fits_existing_methodology === true}
                    >
                      {generate.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                      <span>Generate Draft Methodology</span>
                    </button>
                  )}
                </div>
                {gm.gap_analysis?.fits_existing_methodology === true && (
                  <p className="text-sm text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/30 p-3 rounded border border-amber-100 dark:border-amber-900">
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
              <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-surface-500 dark:text-surface-400">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <MethodologyDraftViewer gm={gm} />
                <div className="flex items-center space-x-3">
                  <button
                    className="btn-secondary"
                    onClick={() => setStep(2)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="btn-primary"
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
              <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-surface-500 dark:text-surface-400">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <QuantificationScaffoldViewer gm={gm} />
                <div className="flex items-center space-x-3">
                  <button
                    className="btn-secondary"
                    onClick={() => setStep(3)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  <button
                    className="btn-primary"
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
              <div className="flex items-center space-x-2 text-surface-500 dark:text-surface-400">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </div>
            ) : !gm ? (
              <p className="text-surface-500 dark:text-surface-400">No methodology record found.</p>
            ) : (
              <div className="space-y-4">
                <div className="text-sm text-surface-700 dark:text-surface-300">
                  Current status: <strong className="uppercase">{gm.status.replace(/_/g, ' ')}</strong>
                </div>

                <div>
                  <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1.5">
                    Rejection / revision reason
                  </label>
                  <textarea
                    className="input-modern"
                    rows={3}
                    placeholder="Required when rejecting or requesting revisions"
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    className="btn-primary"
                    onClick={() => handleStatus('under_review')}
                    disabled={anyLoading || gm.status !== 'draft'}
                  >
                    {updateStatus.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>Submit for Review</span>
                  </button>
                  <button
                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-500 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleStatus('approved')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Approve
                  </button>
                  <button
                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-red-600 text-white font-medium rounded-xl hover:bg-red-500 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleStatus('rejected')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Reject
                  </button>
                  <button
                    className="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-amber-600 text-white font-medium rounded-xl hover:bg-amber-500 active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleStatus('revision_requested')}
                    disabled={anyLoading || gm.status !== 'under_review'}
                  >
                    Request Revision
                  </button>
                </div>

                <div className="flex items-center space-x-3 pt-2">
                  <button
                    className="btn-secondary"
                    onClick={() => setStep(4)}
                    disabled={anyLoading}
                  >
                    Back
                  </button>
                  {gm.methodology && (
                    <button
                      className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-emerald-600 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
