import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { InboxPage } from '../pages/command/InboxPage'
import { useReviewQueue, useUpdateReviewQueueItem } from '../hooks/useReviewQueue'
import { useDecisionAudit } from '../hooks/useDecisionAudit'
import { useCommandWebSocket } from '../hooks/useCommandWebSocket'
import { renderWithRouter } from './test-utils'

vi.mock('../hooks/useReviewQueue', () => ({
  useReviewQueue: vi.fn(),
  useUpdateReviewQueueItem: vi.fn(),
  useDeleteReviewQueueItem: vi.fn(),
}))

vi.mock('../hooks/useDecisionAudit', () => ({
  useDecisionAudit: vi.fn(),
}))

vi.mock('../hooks/useCommandWebSocket', () => ({
  useCommandWebSocket: vi.fn(),
}))

const queueItems = [
  {
    id: 'rq-1',
    item_type: 'agent_review',
    item_id: 'item-1',
    reason: 'Agent confidence below threshold for calculation run',
    priority: 4,
    assigned_to: null,
    status: 'pending',
    resolution_notes: null,
    created_at: '2026-11-03T06:00:00Z',
    resolved_at: null,
  },
]

const decision = {
  id: 'dec-1',
  decision_id: '11111111-1111-1111-1111-111111111111',
  project_id: 'proj-1',
  agent_type: 'calculation_agent',
  action: 'escalate',
  confidence_score: 0.62,
  reasoning: 'Confidence 0.62 is below the project threshold of 0.75.',
  input_summary: null,
  context_package: { estimated_credits: 1250 },
  prev_hash: null,
  record_hash: 'abc123',
  created_at: '2026-11-03T06:00:01Z',
  actor: 'agent:calculation_agent',
  review_queue_item_id: 'rq-1',
}

describe('InboxPage decision audit enrichment', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(useCommandWebSocket as any).mockReturnValue({ send: vi.fn(), connected: true })
    ;(useReviewQueue as any).mockReturnValue({ data: queueItems, isLoading: false, isError: false, error: null })
    ;(useUpdateReviewQueueItem as any).mockReturnValue({ mutate: vi.fn(), isPending: false })
  })

  it('renders agent reasoning block after fetching the decision audit', () => {
    (useDecisionAudit as any).mockReturnValue({ data: decision, isLoading: false, isError: false })

    renderWithRouter(<InboxPage />)

    // Select the agent_review row, then open the audit
    fireEvent.click(screen.getByText('Agent confidence below threshold for calculation run'))
    fireEvent.click(screen.getByRole('button', { name: /decision audit/i }))

    expect(screen.getByText('Agent Reasoning')).toBeInTheDocument()
    expect(screen.getByText('Confidence 0.62 is below the project threshold of 0.75.')).toBeInTheDocument()
    expect(screen.getByText('Confidence: 62%')).toBeInTheDocument()
    expect(screen.getByText('1,250 credits')).toBeInTheDocument()
    expect(useDecisionAudit).toHaveBeenCalledWith('rq-1', true)
  })

  it('shows a fallback when no decision record matches the item', () => {
    (useDecisionAudit as any).mockReturnValue({ data: null, isLoading: false, isError: false })

    renderWithRouter(<InboxPage />)

    fireEvent.click(screen.getByText('Agent confidence below threshold for calculation run'))
    fireEvent.click(screen.getByRole('button', { name: /decision audit/i }))

    expect(screen.getByText('No decision record found for this item')).toBeInTheDocument()
  })

  it('does not show the decision audit button for non-agent item types', () => {
    (useReviewQueue as any).mockReturnValue({
      data: [{ ...queueItems[0], item_type: 'report' }],
      isLoading: false,
      isError: false,
      error: null,
    })
    ;(useDecisionAudit as any).mockReturnValue({ data: null, isLoading: false, isError: false })

    renderWithRouter(<InboxPage />)

    fireEvent.click(screen.getByText('Agent confidence below threshold for calculation run'))
    expect(screen.queryByRole('button', { name: /decision audit/i })).not.toBeInTheDocument()
  })
})
