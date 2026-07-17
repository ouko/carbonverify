import type { WorkflowGraph } from '../types'

export interface WorkflowTemplate {
  name: string
  description: string
  graph: WorkflowGraph
}

const defaultRetryPolicy = {
  max_retries: 3,
  backoff_multiplier: 2,
  initial_delay_ms: 500,
  retry_on: ['timeout', 'connection_error', 'rate_limit'],
}

const defaultCircuitBreaker = {
  failure_threshold: 5,
  recovery_timeout_ms: 30000,
  half_open_max_calls: 3,
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    name: 'Document quality gate',
    description: 'Score project documentation with AI and notify on failure.',
    graph: {
      version: '1.0',
      description: 'AI-led documentation quality gate',
      entry_step: 'evaluate_docs',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'evaluate_docs',
          name: 'Evaluate documentation',
          type: 'ai_evaluation',
          enabled: true,
          config: {
            prompt:
              'Rate the completeness and clarity of the project documentation on a scale of 0.0 to 1.0. Return score, passed, reasoning, and recommendation.',
            input_data: { document_summary: '${document_summary}' },
            pass_threshold: 0.75,
            fail_on_error: true,
            temperature: 0.2,
            max_tokens: 1024,
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_team'],
          timeout_ms: 60000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_team',
          name: 'Notify team',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Documentation quality gate failed',
            body: 'The AI evaluation step failed. Please review the project documentation.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { document_summary: '' },
      human_gates_required: false,
    },
  },
  {
    name: 'Data source completeness check',
    description: 'Verify expected data rows exist and flag missing data.',
    graph: {
      version: '1.0',
      description: 'Check that required data sources have expected row counts',
      entry_step: 'count_rows',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'count_rows',
          name: 'Count data rows',
          type: 'database_query',
          enabled: true,
          config: {
            query: 'SELECT COUNT(*) FROM data_sources WHERE project_id = :project_id',
            params: { project_id: '${project_id}' },
            expected_row_count: null,
            snapshot_result: true,
          },
          next_on_success: ['check_threshold'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'check_threshold',
          name: 'Check row threshold',
          type: 'decision_gate',
          enabled: true,
          config: {
            condition_expression: 'len(rows) >= 1',
            require_human_approval: false,
            auto_approve_threshold: 0.95,
            timeout_seconds: 300,
            escalation_level: 'l1_operator',
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_missing_data'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_missing_data',
          name: 'Notify missing data',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Missing data sources',
            body: 'The project does not have any registered data sources.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { project_id: '' },
      human_gates_required: false,
    },
  },
  {
    name: 'HTTP health check + notify',
    description: 'Ping an endpoint and send a notification on failure.',
    graph: {
      version: '1.0',
      description: 'HTTP health check with failure notification',
      entry_step: 'ping_endpoint',
      retry_policy: defaultRetryPolicy,
      circuit_breaker: defaultCircuitBreaker,
      steps: [
        {
          id: 'ping_endpoint',
          name: 'Ping endpoint',
          type: 'http_request',
          enabled: true,
          config: {
            method: 'GET',
            url: '${health_url}',
            headers: {},
            body: null,
            timeout_ms: 10000,
            expected_status_codes: [200],
            capture_response: true,
          },
          next_on_success: ['end'],
          next_on_failure: ['notify_failure'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
        {
          id: 'notify_failure',
          name: 'Notify failure',
          type: 'notification',
          enabled: true,
          config: {
            channel: 'email',
            recipients: ['operator@carbonverify.demo'],
            subject: 'Health check failed',
            body: 'The health check endpoint did not return 200.',
            priority: 'high',
          },
          next_on_success: ['fail'],
          next_on_failure: ['fail'],
          timeout_ms: 30000,
          capture_proof: true,
          checkpoint: false,
          skippable: false,
        },
      ],
      variables: { health_url: 'https://example.com/health' },
      human_gates_required: false,
    },
  },
]

export function loadWorkflowTemplate(name: string): WorkflowGraph | undefined {
  return WORKFLOW_TEMPLATES.find((t) => t.name === name)?.graph
}
