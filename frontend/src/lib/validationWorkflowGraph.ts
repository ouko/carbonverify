import type { WorkflowGraph, WorkflowStep } from '../types'
import type { ValidationIssue } from '../components/validation-workflow-builder/ValidationIssuesPanel'

const ID_PATTERN = /^[a-zA-Z0-9_-]+$/

export function validateWorkflowGraph(graph: WorkflowGraph): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const stepIds = new Set<string>()
  const duplicates = new Set<string>()

  graph.steps.forEach((step) => {
    if (stepIds.has(step.id)) {
      duplicates.add(step.id)
    } else {
      stepIds.add(step.id)
    }
  })

  duplicates.forEach((id) => issues.push({ type: 'error', message: `Step ID "${id}" is used more than once.` }))

  graph.steps.forEach((step) => {
    if (!step.id) issues.push({ type: 'error', message: 'Step ID is required.', stepId: step.id })
    if (!step.name) issues.push({ type: 'error', message: 'Step name is required.', stepId: step.id })
    if (!ID_PATTERN.test(step.id)) {
      issues.push({ type: 'error', message: 'Step ID may only contain letters, numbers, underscores, and hyphens.', stepId: step.id })
    }
    if (step.timeout_ms < 1000) {
      issues.push({ type: 'error', message: 'Timeout must be at least 1000 ms.', stepId: step.id })
    }
  })

  if (!graph.entry_step) {
    issues.push({ type: 'error', message: 'Entry step is required.' })
  } else if (!stepIds.has(graph.entry_step)) {
    issues.push({ type: 'error', message: `Entry step "${graph.entry_step}" does not exist.` })
  }

  graph.steps.forEach((step) => {
    [...step.next_on_success, ...step.next_on_failure].forEach((ref) => {
      if (ref !== 'end' && ref !== 'fail' && !stepIds.has(ref)) {
        issues.push({ type: 'error', message: `Reference to unknown step "${ref}".`, stepId: step.id })
      }
    })
  })

  const reachable = new Set<string>()
  const visit = (id: string) => {
    if (reachable.has(id)) return
    reachable.add(id)
    const step = graph.steps.find((s) => s.id === id)
    if (!step) return
    [...step.next_on_success, ...step.next_on_failure].forEach((ref) => {
      if (ref !== 'end' && ref !== 'fail') visit(ref)
    })
  }
  if (graph.entry_step && stepIds.has(graph.entry_step)) visit(graph.entry_step)

  graph.steps.forEach((step) => {
    if (!reachable.has(step.id)) {
      issues.push({ type: 'warning', message: `Step "${step.id}" is not reachable from the entry step.`, stepId: step.id })
    }
  })

  validateStepConfig(graph.steps, issues)

  return issues
}

function validateStepConfig(steps: WorkflowStep[], issues: ValidationIssue[]) {
  steps.forEach((step) => {
    const cfg = step.config
    switch (step.type) {
      case 'ai_evaluation': {
        const prompt = cfg.prompt as string | undefined
        if (!prompt || prompt.length < 1) {
          issues.push({ type: 'error', message: 'Prompt is required.', stepId: step.id })
        }
        const threshold = cfg.pass_threshold as number | undefined
        if (threshold !== undefined && (threshold < 0 || threshold > 1)) {
          issues.push({ type: 'error', message: 'Pass threshold must be between 0.0 and 1.0.', stepId: step.id })
        }
        const tokens = cfg.max_tokens as number | undefined
        if (tokens !== undefined && (tokens < 100 || tokens > 8192)) {
          issues.push({ type: 'error', message: 'Max tokens must be between 100 and 8192.', stepId: step.id })
        }
        break
      }
      case 'http_request': {
        if (!cfg.url) issues.push({ type: 'error', message: 'URL is required.', stepId: step.id })
        const method = cfg.method as string
        if (!['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'].includes(method)) {
          issues.push({ type: 'error', message: 'Invalid HTTP method.', stepId: step.id })
        }
        break
      }
      case 'database_query': {
        const query = cfg.query as string
        if (!query) issues.push({ type: 'error', message: 'Query is required.', stepId: step.id })
        else if (!/^\s*SELECT\s/i.test(query)) {
          issues.push({ type: 'error', message: 'Only SELECT queries are allowed.', stepId: step.id })
        }
        break
      }
      case 'decision_gate': {
        if (!cfg.condition_expression) {
          issues.push({ type: 'error', message: 'Condition expression is required.', stepId: step.id })
        }
        break
      }
      case 'wait': {
        const duration = cfg.duration_ms as number
        if (duration === undefined || duration < 0) {
          issues.push({ type: 'error', message: 'Wait duration must be >= 0.', stepId: step.id })
        }
        break
      }
      case 'parallel': {
        const branches = cfg.branches as string[] | undefined
        if (!branches || branches.length < 2) {
          issues.push({ type: 'error', message: 'Parallel step needs at least 2 branches.', stepId: step.id })
        }
        break
      }
      case 'subflow': {
        if (!cfg.workflow_name) issues.push({ type: 'error', message: 'Workflow name is required.', stepId: step.id })
        break
      }
    }
  })
}
