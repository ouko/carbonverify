import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import LeadsPage from '../pages/LeadsPage'
import { api } from '../services/api'
import type { Lead } from '../types'
import type { LeadDocument } from '../hooks/useLeads'

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockLead: Lead = {
  id: 'lead-1',
  registry_source: 'verra',
  external_id: 'VCS-VCU-1234',
  project_name: 'Test Project',
  project_developer: 'Test Developer',
  developer_contact: null,
  developer_email: null,
  country: 'Kenya',
  region: null,
  methodology: 'VM0050',
  sector: 'Agriculture',
  status: 'registered',
  crediting_period_start: '2020-01-01',
  crediting_period_end: '2030-01-01',
  last_verification_date: null,
  last_monitoring_period_end: null,
  estimated_credits_per_year: 10000,
  registry_url: 'https://registry.example/1234',
  days_in_status: 5,
  stuck_score: 42.5,
  priority: 'high',
  lead_status: 'new',
  notes: null,
  scraped_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  last_scored_at: null,
  assigned_to: null,
}

const mockDocuments: LeadDocument[] = [
  {
    id: 'doc-1',
    lead_id: 'lead-1',
    document_type: 'project_design_document',
    source_url: 'https://registry.example/1234/pdd.pdf',
    title: 'Project Design Document',
    status: 'fetched',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'doc-2',
    lead_id: 'lead-1',
    document_type: 'monitoring_report',
    source_url: 'https://registry.example/1234/mr.pdf',
    title: 'Monitoring Report',
    status: 'discovered',
    created_at: '2024-01-01T00:00:00Z',
  },
]

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LeadsPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('LeadDocuments', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders documents panel with fetched docs', async () => {
    const mockedGet = vi.mocked(api.get)
    mockedGet.mockImplementation((url: string) => {
      if (url.startsWith('/leads/?')) {
        return Promise.resolve({ data: [mockLead] })
      }
      if (url === '/leads/lead-1/documents') {
        return Promise.resolve({ data: mockDocuments })
      }
      return Promise.resolve({ data: [] })
    })

    renderPage()

    fireEvent.click(await screen.findByText('Test Project'))

    expect(await screen.findByText('Documents')).toBeInTheDocument()
    expect(await screen.findByText('Project Design Document')).toBeInTheDocument()
    expect(await screen.findByText('Monitoring Report')).toBeInTheDocument()
    expect(screen.getByText('fetched')).toBeInTheDocument()
    expect(screen.getByText('discovered')).toBeInTheDocument()
  })

  it('clicking Fetch Documents calls the API and invalidates the query', async () => {
    const mockedGet = vi.mocked(api.get)
    const mockedPost = vi.mocked(api.post)

    mockedGet.mockImplementation((url: string) => {
      if (url.startsWith('/leads/?')) {
        return Promise.resolve({ data: [mockLead] })
      }
      if (url === '/leads/lead-1/documents') {
        return Promise.resolve({ data: mockDocuments })
      }
      return Promise.resolve({ data: [] })
    })

    mockedPost.mockResolvedValue({ data: { message: 'queued', lead_id: 'lead-1' } })

    renderPage()

    fireEvent.click(await screen.findByText('Test Project'))
    expect(await screen.findByText('Project Design Document')).toBeInTheDocument()

    const documentRequestsBefore = mockedGet.mock.calls.filter((call) => call[0] === '/leads/lead-1/documents').length

    fireEvent.click(screen.getByRole('button', { name: /Fetch Documents/i }))

    await waitFor(() => {
      expect(mockedPost).toHaveBeenCalledWith('/leads/lead-1/fetch-documents')
    })

    await waitFor(() => {
      const documentRequestsAfter = mockedGet.mock.calls.filter((call) => call[0] === '/leads/lead-1/documents').length
      expect(documentRequestsAfter).toBeGreaterThan(documentRequestsBefore)
    })
  })
})
