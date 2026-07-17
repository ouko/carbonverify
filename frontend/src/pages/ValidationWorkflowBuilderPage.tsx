import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Save, Play, Loader2, ArrowLeft } from 'lucide-react'
import { StepPalette } from '../components/validation-workflow-builder/StepPalette'
import { StepList } from '../components/validation-workflow-builder/StepList'
import { GraphPreview } from '../components/validation-workflow-builder/GraphPreview'
import { StepConfigPanel } from '../components/validation-workflow-builder/StepConfigPanel'
import { WorkflowSettingsPanel } from '../components/validation-workflow-builder/WorkflowSettingsPanel'
import { RunWorkflowPanel } from '../components/validation-workflow-builder/RunWorkflowPanel'
import { ValidationIssuesPanel } from '../components/validation-workflow-builder/ValidationIssuesPanel'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useWorkflow, useCreateWorkflow, useUpdateWorkflow } from '../hooks/useValidationWorkflows'
import { loadWorkflowTemplate } from '../lib/validationWorkflowTemplates'
import { validateWorkflowGraph } from '../lib/validationWorkflowGraph'
import type { WorkflowGraph, WorkflowStep, WorkflowStepType } from '../types'

const DEFAULT_GRAPH: WorkflowGraph = {
  version: '1.0',
  description: '',
  entry_step: '',
  retry_policy: { max_retries: 3, backoff_multiplier: 2, initial_delay_ms: 500, retry_on: ['timeout', 'connection_error', 'rate_limit'] },
  circuit_breaker: { failure_threshold: 5, recovery_timeout_ms: 30000, half_open_max_calls: 3 },
  steps: [],
  variables: {},
  human_gates_required: false,
}

function makeEmptyStep(type: WorkflowStepType, index: number): WorkflowStep {
  return {
    id: `${type}_${index + 1}`,
    name: `${type} step`,
    type,
    description: '',
    enabled: true,
    config: {},
    next_on_success: [],
    next_on_failure: [],
    timeout_ms: 60000,
    capture_proof: true,
    checkpoint: false,
    skippable: false,
  }
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    return axiosErr.response?.data?.detail || 'An unexpected error occurred'
  }
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export default function ValidationWorkflowBuilderPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isNew = id === 'new'
  const { data: existingWorkflow, isLoading } = useWorkflow(isNew ? undefined : id)
  const createWorkflow = useCreateWorkflow()
  const updateWorkflow = useUpdateWorkflow(id || '')

  const [name, setName] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [description, setDescription] = useState('')
  const [graph, setGraph] = useState<WorkflowGraph>(DEFAULT_GRAPH)
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'step' | 'settings'>('settings')
  const [error, setError] = useState<string | null>(null)
  const [showRunPanel, setShowRunPanel] = useState(false)

  useEffect(() => {
    if (existingWorkflow) {
      setName(existingWorkflow.name)
      setVersion(existingWorkflow.version)
      setDescription(existingWorkflow.description || '')
      setGraph(existingWorkflow.workflow_graph as WorkflowGraph)
    }
  }, [existingWorkflow])

  const issues = useMemo(() => validateWorkflowGraph(graph), [graph])
  const hasErrors = issues.some((i) => i.type === 'error')

  const addStep = (type: WorkflowStepType) => {
    const newStep = makeEmptyStep(type, graph.steps.length)
    setGraph((g) => ({ ...g, steps: [...g.steps, newStep] }))
    if (!graph.entry_step) setGraph((g) => ({ ...g, entry_step: newStep.id }))
    setSelectedStepId(newStep.id)
    setActiveTab('step')
  }

  const loadTemplate = (templateName: string) => {
    const templateGraph = loadWorkflowTemplate(templateName)
    if (templateGraph) {
      setGraph(templateGraph)
      setSelectedStepId(null)
      setActiveTab('settings')
    }
  }

  const updateStep = (updatedStep: WorkflowStep) => {
    setGraph((g) => ({
      ...g,
      steps: g.steps.map((s) => (s.id === updatedStep.id ? updatedStep : s)),
    }))
  }

  const removeStep = (stepId: string) => {
    setGraph((g) => ({
      ...g,
      steps: g.steps.filter((s) => s.id !== stepId),
      entry_step: g.entry_step === stepId ? '' : g.entry_step,
    }))
    if (selectedStepId === stepId) setSelectedStepId(null)
  }

  const moveStep = (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= graph.steps.length) return
    const next = [...graph.steps]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    setGraph((g) => ({ ...g, steps: next }))
  }

  const handleSave = async () => {
    setError(null)
    if (hasErrors) return
    try {
      const payload = { name, version, description, workflow_graph: graph }
      if (isNew) {
        const created = await createWorkflow.mutateAsync(payload)
        navigate(`/validation-workflows/${created.id}/builder`, { replace: true })
      } else {
        await updateWorkflow.mutateAsync({ workflow_graph: graph, description })
      }
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const selectedStep = graph.steps.find((s) => s.id === selectedStepId) || null

  if (isLoading) return <LoadingSpinner fullscreen />

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <header className="flex items-center justify-between px-6 py-3 border-b border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/validation-workflows')} className="btn-ghost p-2">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="page-title text-lg">{isNew ? 'New Workflow' : name}</h1>
            <p className="text-xs text-surface-500 dark:text-surface-400">
              {graph.steps.length} step{graph.steps.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowRunPanel((s) => !s)} className="btn-secondary flex items-center gap-2">
            <Play className="w-4 h-4" /> Run
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={createWorkflow.isPending || updateWorkflow.isPending || hasErrors}
            className="btn-primary flex items-center gap-2"
          >
            {(createWorkflow.isPending || updateWorkflow.isPending) && <Loader2 className="w-4 h-4 animate-spin" />}
            <Save className="w-4 h-4" /> Save
          </button>
        </div>
      </header>

      {error && <div className="mx-6 mt-4 card border-l-4 border-l-red-500 p-3 text-sm text-red-700 dark:text-red-300">{error}</div>}
      <div className="mx-6 mt-4">
        <ValidationIssuesPanel issues={issues} />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-0 overflow-hidden">
        <div className="lg:col-span-2 border-r border-surface-200 dark:border-surface-700 overflow-y-auto">
          <StepPalette onAddStep={addStep} onLoadTemplate={loadTemplate} />
        </div>

        <div className="lg:col-span-5 border-r border-surface-200 dark:border-surface-700 overflow-y-auto">
          <StepList
            steps={graph.steps}
            selectedId={selectedStepId}
            entryStep={graph.entry_step}
            onSelect={(id) => {
              setSelectedStepId(id)
              setActiveTab('step')
            }}
            onRemove={removeStep}
            onMove={moveStep}
          />
          <GraphPreview graph={graph} />
        </div>

        <div className="lg:col-span-5 overflow-y-auto">
          <div className="flex border-b border-surface-200 dark:border-surface-700">
            <button
              onClick={() => setActiveTab('settings')}
              className={`flex-1 py-2 text-sm font-medium ${activeTab === 'settings' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-surface-500'}`}
            >
              Workflow
            </button>
            <button
              onClick={() => setActiveTab('step')}
              disabled={!selectedStep}
              className={`flex-1 py-2 text-sm font-medium ${activeTab === 'step' ? 'text-primary-600 border-b-2 border-primary-600' : 'text-surface-500'}`}
            >
              Step
            </button>
          </div>

          {activeTab === 'settings' ? (
            <WorkflowSettingsPanel
              name={name}
              version={version}
              description={description}
              graph={graph}
              onChangeName={setName}
              onChangeVersion={setVersion}
              onChangeDescription={setDescription}
              onChangeGraph={setGraph}
            />
          ) : (
            <StepConfigPanel step={selectedStep} graph={graph} onChangeStep={updateStep} onRemoveStep={removeStep} />
          )}

          {showRunPanel && existingWorkflow && (
            <RunWorkflowPanel
              workflow={existingWorkflow}
              onRunCreated={(run) => {
                navigate(`/validation-workflows/${existingWorkflow.id}/runs/${run.id}`)
              }}
            />
          )}
        </div>
      </div>
    </div>
  )
}
