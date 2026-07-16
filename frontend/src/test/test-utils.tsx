import { ReactNode } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { render } from '@testing-library/react'

const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const

export function renderWithRouter(ui: ReactNode) {
  return render(
    <BrowserRouter future={routerFuture}>
      {ui}
    </BrowserRouter>
  )
}

export { renderWithRouter as render }
