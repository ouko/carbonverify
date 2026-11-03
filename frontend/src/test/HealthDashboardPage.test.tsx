import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { HealthDashboardPage } from '../pages/command/HealthDashboardPage'
import { useHealthScore, useDecisionConfidenceTrend } from '../hooks/useHealthScore'
import { renderWithRouter } from './test-utils'

vi.mock('../hooks/useHealthScore', () => ({
  useHealthScore: vi.fn(),
  useDecisionConfidenceTrend: vi.fn(),
}))

const health = {
  score: 82,
  components: {
    agent_confidence: 91.5,
    open_escalations: { score: 80, open_p0: 0, open_p1: 2, open_p2: 0 },
    review_queue_depth: { score: 95, pending: 1 },
  },
}

describe('HealthDashboardPage', () => {
  it('renders the score gauge and configured component cards', () => {
    (useHealthScore as any).mockReturnValue({ data: health, isLoading: false, isError: false, error: null })
    ;(useDecisionConfidenceTrend as any).mockReturnValue({
      data: [{ day: '2026-11-01', confidence: 88.2 }],
      isLoading: false,
    })

    renderWithRouter(<HealthDashboardPage />)

    expect(screen.getByText('82')).toBeInTheDocument()
    expect(screen.getByText('Degraded')).toBeInTheDocument()
    expect(screen.getByText('Agent Confidence (24h)')).toBeInTheDocument()
    expect(screen.getByText('Open Escalations')).toBeInTheDocument()
    expect(screen.getByText('Review Queue Depth')).toBeInTheDocument()
    // Absent components render as not configured
    expect(screen.getByText('Remediation Resolution (7d)')).toBeInTheDocument()
    expect(screen.getAllByText('not configured')).toHaveLength(2)
    // Detail breakdowns
    expect(screen.getByText('P0: 0 · P1: 2 · P2: 0 open')).toBeInTheDocument()
    expect(screen.getByText('1 pending / in review')).toBeInTheDocument()
  })

  it('renders an error state when the health score fails to load', () => {
    (useHealthScore as any).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('boom'),
    })
    ;(useDecisionConfidenceTrend as any).mockReturnValue({ data: [], isLoading: false })

    renderWithRouter(<HealthDashboardPage />)

    expect(screen.getByText('Failed to load data')).toBeInTheDocument()
  })
})
