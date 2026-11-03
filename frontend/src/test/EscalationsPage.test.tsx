import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { EscalationsPage } from '../pages/command/EscalationsPage'
import {
  useEscalations,
  useEscalationStats,
  useAcknowledgeEscalation,
  useResolveEscalation,
} from '../hooks/useEscalations'
import { useCommandWebSocket } from '../hooks/useCommandWebSocket'
import { renderWithRouter } from './test-utils'

vi.mock('../hooks/useEscalations', () => ({
  useEscalations: vi.fn(),
  useEscalationStats: vi.fn(),
  useAcknowledgeEscalation: vi.fn(),
  useResolveEscalation: vi.fn(),
}))

vi.mock('../hooks/useCommandWebSocket', () => ({
  useCommandWebSocket: vi.fn(),
}))

const mockEvents = [
  {
    id: 'esc-1',
    project_id: 'proj-1',
    source: 'orchestrator',
    title: 'Confidence below threshold',
    detail: 'Agent confidence dropped below the project threshold during calculation review.',
    context_package: { agent_type: 'calculation_agent', run_id: 'run-42' },
    priority: 0,
    severity_score: 8.5,
    status: 'open',
    channels_sent: { email: true, slack: false },
    created_at: '2026-11-03T08:00:00Z',
    acknowledged_at: null,
    acknowledged_by: null,
    resolved_at: null,
    resolved_by: null,
    resolution_notes: null,
  },
  {
    id: 'esc-2',
    project_id: null,
    source: 'validation_engine',
    title: 'Workflow run failed',
    detail: 'Validation run failed at step 3.',
    context_package: {},
    priority: 1,
    severity_score: 5.2,
    status: 'acknowledged',
    channels_sent: { email: true, slack: true },
    created_at: '2026-11-02T10:00:00Z',
    acknowledged_at: '2026-11-02T11:00:00Z',
    acknowledged_by: 'user-1',
    resolved_at: null,
    resolved_by: null,
    resolution_notes: null,
  },
]

const acknowledgeMutate = vi.fn()
const resolveMutate = vi.fn()

describe('EscalationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(useCommandWebSocket as any).mockReturnValue({ send: vi.fn(), connected: true })
    ;(useEscalations as any).mockReturnValue({
      data: { items: mockEvents, total: 2, skip: 0, limit: 50 },
      isLoading: false,
      isError: false,
      error: null,
    })
    ;(useEscalationStats as any).mockReturnValue({
      data: {
        total: 2,
        by_status: { open: 1, acknowledged: 1, resolved: 0 },
        by_priority: { '0': 1, '1': 1, '2': 0 },
        open_p0: 1,
        avg_time_to_ack_seconds: 3600,
      },
      isLoading: false,
    })
    ;(useAcknowledgeEscalation as any).mockReturnValue({ mutate: acknowledgeMutate, isPending: false })
    ;(useResolveEscalation as any).mockReturnValue({ mutate: resolveMutate, isPending: false })
  })

  it('renders the list with priority badges and the stats strip', () => {
    renderWithRouter(<EscalationsPage />)
    expect(screen.getByText('Confidence below threshold')).toBeInTheDocument()
    expect(screen.getByText('Workflow run failed')).toBeInTheDocument()
    expect(screen.getAllByText('P0').length).toBeGreaterThan(0)
    expect(screen.getByText('Open P0')).toBeInTheDocument()
    expect(screen.getByText('1.0h')).toBeInTheDocument() // avg ack time
  })

  it('shows detail panel with context package and delivery channels on selection', () => {
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    expect(screen.getByText('Context Package')).toBeInTheDocument()
    expect(screen.getByText('calculation_agent')).toBeInTheDocument()
    expect(screen.getByText('email: sent')).toBeInTheDocument()
    expect(screen.getByText('slack: not sent')).toBeInTheDocument()
    expect(screen.getByText('Timeline')).toBeInTheDocument()
  })

  it('calls acknowledge mutation with the escalation id', () => {
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    fireEvent.click(screen.getByRole('button', { name: /acknowledge/i }))
    expect(acknowledgeMutate).toHaveBeenCalledWith('esc-1', expect.any(Object))
  })

  it('prompts for notes and calls resolve mutation with notes', async () => {
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    fireEvent.click(screen.getByRole('button', { name: /^resolve$/i }))
    fireEvent.change(screen.getByPlaceholderText('What was done to resolve this escalation?'), {
      target: { value: 'Fixed the threshold config' },
    })
    fireEvent.click(screen.getByRole('button', { name: /confirm resolve/i }))
    await waitFor(() => {
      expect(resolveMutate).toHaveBeenCalledWith(
        { id: 'esc-1', notes: 'Fixed the threshold config' },
        expect.any(Object)
      )
    })
  })

  it('requires resolution notes before confirm resolve is enabled', () => {
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    fireEvent.click(screen.getByRole('button', { name: /^resolve$/i }))
    const confirm = screen.getByRole('button', { name: /confirm resolve/i })
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByPlaceholderText('What was done to resolve this escalation?'), {
      target: { value: 'Restarted the run' },
    })
    expect(confirm).toBeEnabled()
  })

  it('shows a friendly empty state when there are no escalations at all', () => {
    (useEscalations as any).mockReturnValue({
      data: { items: [], total: 0, skip: 0, limit: 50 },
      isLoading: false,
      isError: false,
      error: null,
    })
    renderWithRouter(<EscalationsPage />)
    expect(screen.getByText('No escalations — all systems operating normally')).toBeInTheDocument()
  })

  it('shows a filter-specific empty state when filters exclude everything', () => {
    (useEscalations as any).mockReturnValue({
      data: { items: [], total: 0, skip: 0, limit: 50 },
      isLoading: false,
      isError: false,
      error: null,
    })
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByRole('button', { name: 'P0' }))
    expect(screen.getByText('No escalations match the current filters')).toBeInTheDocument()
  })

  it('keeps the detail panel open with a hint when the selected item leaves the filtered list', () => {
    (useEscalations as any).mockReturnValue({
      data: { items: mockEvents, total: 2, skip: 0, limit: 50 },
      isLoading: false,
      isError: false,
      error: null,
    })
    const { rerender } = renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    expect(screen.getByText('Context Package')).toBeInTheDocument()

    // Simulate a refetch (poll/WebSocket invalidation) where the acknowledged
    // item no longer matches the active filters.
    ;(useEscalations as any).mockReturnValue({
      data: { items: [mockEvents[1]], total: 1, skip: 0, limit: 50 },
      isLoading: false,
      isError: false,
      error: null,
    })
    rerender(
      <BrowserRouter>
        <EscalationsPage />
      </BrowserRouter>
    )

    expect(screen.getByText('Context Package')).toBeInTheDocument()
    expect(screen.getByText('Confidence below threshold')).toBeInTheDocument()
    expect(
      screen.getByText(/no longer matches the active filters/)
    ).toBeInTheDocument()
  })

  it('surfaces acknowledge and resolve mutation errors', () => {
    (useResolveEscalation as any).mockReturnValue({
      mutate: resolveMutate,
      isPending: false,
      isError: true,
      error: { response: { data: { detail: 'Escalation already resolved' } } },
    })
    renderWithRouter(<EscalationsPage />)
    fireEvent.click(screen.getByText('Confidence below threshold'))
    expect(screen.getByRole('alert')).toHaveTextContent('Escalation already resolved')
  })
})
