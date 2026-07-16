import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { render } from './test-utils'
import MethodologyDesignerPage from '../pages/MethodologyDesignerPage'

vi.mock('../hooks/useMethodologyGenerator', () => ({
  useCreateGeneratedMethodology: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGeneratedMethodology: () => ({ data: null, isLoading: false, error: null }),
  useAnalyzeGap: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateMethodology: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateMethodologyStatus: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useMethodologyTemplates: () => ({
    data: [
      {
        id: '11111111-1111-1111-1111-111111111111',
        name: 'Cookstoves / Household Energy',
        sector: 'Cookstoves',
        is_active: true,
        description: 'Test cookstoves template',
        defaults_json: {
          boundaries: {
            geographic_scope: 'Kenya',
            temporal_scope: '2025-2034',
            physical_boundary: 'Households',
            ghg_sources_included: 'CO2, CH4',
          },
          data_sources: [
            {
              source_type: 'survey',
              description: 'Household survey',
              frequency: 'annual',
              provider_quality: 'Third-party',
            },
          ],
        },
      },
    ],
    isLoading: false,
  }),
}))

vi.mock('../hooks/useProjects', () => ({
  useProjects: () => ({ data: [{ id: 'p1', name: 'Test Project' }], isLoading: false }),
}))

function fillContextStep() {
  fireEvent.change(screen.getByLabelText('Project this methodology is for *'), {
    target: { value: 'p1' },
  })
  fireEvent.change(screen.getByLabelText('Methodology name *'), {
    target: { value: 'Test Methodology' },
  })
  fireEvent.change(screen.getByLabelText('Sector / project type *'), {
    target: { value: 'Test Sector' },
  })
  fireEvent.change(screen.getByLabelText('Activity description *'), {
    target: { value: 'A detailed activity description for testing.' },
  })
}

function goToBoundariesStep() {
  fillContextStep()
  fireEvent.click(screen.getByText('Next: Boundaries & Data Sources'))
}

describe('MethodologyDesignerPage', () => {
  it('renders the template selector', () => {
    render(<MethodologyDesignerPage />)
    expect(screen.getByText('Cookstoves / Household Energy')).toBeInTheDocument()
  })

  it('pre-fills form when a template is selected', async () => {
    render(<MethodologyDesignerPage />)
    fireEvent.click(screen.getByText('Cookstoves / Household Energy'))
    await waitFor(() => {
      expect(screen.getByDisplayValue('Cookstoves')).toBeInTheDocument()
    })

    goToBoundariesStep()
    await waitFor(() => {
      expect(screen.getByDisplayValue('Kenya')).toBeInTheDocument()
    })
  })

  it('hides advanced fields by default', async () => {
    render(<MethodologyDesignerPage />)
    goToBoundariesStep()
    await waitFor(() => {
      expect(
        screen.queryByLabelText('Greenhouse gases covered (optional)')
      ).not.toBeInTheDocument()
    })
  })

  it('shows advanced fields when toggle is clicked', async () => {
    render(<MethodologyDesignerPage />)
    goToBoundariesStep()
    await waitFor(() => {
      expect(screen.getByText('Show advanced fields')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('Show advanced fields'))
    await waitFor(() => {
      expect(screen.getByLabelText('Greenhouse gases covered (optional)')).toBeInTheDocument()
    })
  })

  it('shows validation errors for empty required fields', async () => {
    render(<MethodologyDesignerPage />)
    fireEvent.click(screen.getByText('Next: Boundaries & Data Sources'))
    await waitFor(() => {
      expect(screen.getByText('Please fix the highlighted fields.')).toBeInTheDocument()
      expect(screen.getByText('Please select a linked project.')).toBeInTheDocument()
      expect(screen.getByText('Methodology name is required.')).toBeInTheDocument()
      expect(screen.getByText('Sector is required.')).toBeInTheDocument()
    })
  })
})
