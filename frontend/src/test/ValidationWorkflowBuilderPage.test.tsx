import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ValidationWorkflowBuilderPage from '../pages/ValidationWorkflowBuilderPage'

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: { id: 'wf-1' } })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

function renderPage(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/validation-workflows/:id/builder" element={<ValidationWorkflowBuilderPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ValidationWorkflowBuilderPage', () => {
  it('renders the new workflow builder', () => {
    renderPage('/validation-workflows/new/builder')
    expect(screen.getByText('New Workflow')).toBeInTheDocument()
    expect(screen.getByText('Step Types')).toBeInTheDocument()
  })

  it('adds a step when a palette item is clicked', () => {
    renderPage('/validation-workflows/new/builder')
    fireEvent.click(screen.getByText('AI Evaluation'))
    expect(screen.getAllByText('ai_evaluation_1')).not.toHaveLength(0)
  })
})
