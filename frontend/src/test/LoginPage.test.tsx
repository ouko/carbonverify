import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import LoginPage from '../pages/LoginPage'
import { useAuthStore } from '../stores/authStore'
import { renderWithRouter } from './test-utils'

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  }
})

describe('LoginPage', () => {
  const mockLogin = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    ;(useAuthStore as any).mockImplementation((selector: any) =>
      selector ? selector({ login: mockLogin }) : { login: mockLogin }
    )
  })

  it('renders login form with email and password inputs', () => {
    renderWithRouter(<LoginPage />)

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows error message when login fails', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))

    renderWithRouter(<LoginPage />)

    const form = document.querySelector('form')!
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: 'test@example.com' },
    })
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'wrongpassword' },
    })
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
    })
  })

  it('toggles password visibility', () => {
    renderWithRouter(<LoginPage />)

    const passwordInput = screen.getByPlaceholderText('••••••••') as HTMLInputElement
    expect(passwordInput.type).toBe('password')

    fireEvent.click(screen.getByRole('button', { name: /show password|hide password/i }))
    expect(passwordInput.type).toBe('text')
  })
})
