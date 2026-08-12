import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import ProjectDetailPage from '../pages/ProjectDetailPage'
import { useProject, useProjectPreAudit } from '../hooks/useProjects'
import { renderWithRouter } from './test-utils'

vi.mock('../hooks/useProjects', () => ({
  useProject: vi.fn(),
  useProjectPreAudit: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'test-project-id' }),
  }
})

const mockProject = {
  id: 'test-project-id',
  name: 'Test Project',
  status: 'data_collection',
  methodology: 'VM0050',
  complexity_score: 3,
  confidence_threshold: 0.75,
}

describe('ProjectDetailPage pre-audit panel', () => {
  it('renders pre-audit readiness score and recommendation', () => {
    (useProject as any).mockReturnValue({
      data: mockProject,
      isLoading: false,
      isError: false,
      error: null,
    })
    ;(useProjectPreAudit as any).mockReturnValue({
      data: {
        id: 'pre-audit-1',
        project_id: 'test-project-id',
        readiness_score: 0.82,
        status: 'passed',
        gap_summary: {
          recommendation: 'Project is ready for formal audit submission.',
        },
        created_at: '2026-08-12T00:00:00Z',
      },
    })

    renderWithRouter(<ProjectDetailPage />)

    expect(screen.getByText(/Pre-audit readiness: 82% \(passed\)/)).toBeInTheDocument()
    expect(screen.getByText(/Project is ready for formal audit submission./)).toBeInTheDocument()
  })

  it('renders gaps and risk flags when present', () => {
    (useProject as any).mockReturnValue({
      data: mockProject,
      isLoading: false,
      isError: false,
      error: null,
    })
    ;(useProjectPreAudit as any).mockReturnValue({
      data: {
        id: 'pre-audit-2',
        project_id: 'test-project-id',
        readiness_score: 0.55,
        status: 'failed',
        gap_summary: {
          recommendation: 'Address documentation gaps before submission.',
          gaps: ['Missing baseline scenario', 'Incomplete monitoring plan'],
          risk_flags: ['High regulatory risk'],
        },
        created_at: '2026-08-12T00:00:00Z',
      },
    })

    renderWithRouter(<ProjectDetailPage />)

    expect(screen.getByText(/Pre-audit readiness: 55% \(failed\)/)).toBeInTheDocument()
    expect(screen.getByText(/Address documentation gaps before submission./)).toBeInTheDocument()
    expect(screen.getByText(/Missing baseline scenario/)).toBeInTheDocument()
    expect(screen.getByText(/Incomplete monitoring plan/)).toBeInTheDocument()
    expect(screen.getByText(/High regulatory risk/)).toBeInTheDocument()
  })

  it('does not render the panel when no pre-audit exists', () => {
    (useProject as any).mockReturnValue({
      data: mockProject,
      isLoading: false,
      isError: false,
      error: null,
    })
    ;(useProjectPreAudit as any).mockReturnValue({ data: null })

    renderWithRouter(<ProjectDetailPage />)

    expect(screen.queryByText(/Pre-audit readiness/)).not.toBeInTheDocument()
  })
})
