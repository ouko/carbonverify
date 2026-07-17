import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type {
  ValidationWorkflow,
  ValidationWorkflowCreatePayload,
  ValidationWorkflowUpdatePayload,
  ValidationRun,
  RunTriggerPayload,
  StepExecution,
  ValidationProof,
  ValidationTransition,
  SyntheticActor,
} from '../types'

const WORKFLOWS_KEY = ['validation-workflows']
const workflowKey = (id: string) => ['validation-workflows', id]
const runsKey = (workflowId: string) => ['validation-runs', workflowId]
const runKey = (runId: string) => ['validation-run', runId]
const actorsKey = ['synthetic-actors']

export function useWorkflows() {
  return useQuery<ValidationWorkflow[]>({
    queryKey: WORKFLOWS_KEY,
    queryFn: async () => {
      const res = await api.get('/validation/workflows')
      return res.data
    },
  })
}

export function useWorkflow(id: string | undefined) {
  return useQuery<ValidationWorkflow>({
    queryKey: workflowKey(id || ''),
    queryFn: async () => {
      const res = await api.get(`/validation/workflows/${id}`)
      return res.data
    },
    enabled: !!id,
  })
}

export function useCreateWorkflow() {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, ValidationWorkflowCreatePayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/validation/workflows', payload)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: WORKFLOWS_KEY }),
  })
}

export function useUpdateWorkflow(id: string) {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, ValidationWorkflowUpdatePayload>({
    mutationFn: async (payload) => {
      const res = await api.patch(`/validation/workflows/${id}`, payload)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey(id) })
      qc.invalidateQueries({ queryKey: WORKFLOWS_KEY })
    },
  })
}

export function useToggleWorkflowActive(id: string) {
  const qc = useQueryClient()
  return useMutation<ValidationWorkflow, unknown, boolean>({
    mutationFn: async (active) => {
      const res = await api.patch(`/validation/workflows/${id}`, { active })
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: workflowKey(id) })
      qc.invalidateQueries({ queryKey: WORKFLOWS_KEY })
    },
  })
}

export function useValidationRuns(workflowId: string | undefined) {
  return useQuery<ValidationRun[]>({
    queryKey: runsKey(workflowId || ''),
    queryFn: async () => {
      const res = await api.get('/validation/runs', { params: { workflow_id: workflowId } })
      return res.data
    },
    enabled: !!workflowId,
  })
}

export function useValidationRun(runId: string | undefined) {
  return useQuery<ValidationRun>({
    queryKey: runKey(runId || ''),
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}`)
      return res.data
    },
    enabled: !!runId,
    refetchInterval: (query) =>
      query.state.data &&
      !['completed', 'failed', 'archived'].includes(query.state.data.status)
        ? 2000
        : false,
  })
}

export function useTriggerRun() {
  const qc = useQueryClient()
  return useMutation<ValidationRun, unknown, RunTriggerPayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/validation/runs', payload)
      return res.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: runsKey(data.workflow_id) })
    },
  })
}

export function useCancelRun() {
  const qc = useQueryClient()
  return useMutation<ValidationRun, unknown, string>({
    mutationFn: async (runId) => {
      const res = await api.post(`/validation/runs/${runId}/cancel`)
      return res.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: runKey(data.id) })
      qc.invalidateQueries({ queryKey: runsKey(data.workflow_id) })
    },
  })
}

export function useStepExecutions(runId: string | undefined) {
  return useQuery<StepExecution[]>({
    queryKey: ['validation-run-steps', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/steps`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useProofs(runId: string | undefined) {
  return useQuery<ValidationProof[]>({
    queryKey: ['validation-run-proofs', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/proofs`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useTransitions(runId: string | undefined) {
  return useQuery<ValidationTransition[]>({
    queryKey: ['validation-run-transitions', runId || ''],
    queryFn: async () => {
      const res = await api.get(`/validation/runs/${runId}/transitions`)
      return res.data
    },
    enabled: !!runId,
  })
}

export function useSyntheticActors() {
  return useQuery<SyntheticActor[]>({
    queryKey: actorsKey,
    queryFn: async () => {
      const res = await api.get('/validation/synthetic-actors')
      return res.data
    },
  })
}
