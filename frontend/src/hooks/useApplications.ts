import { useMutation } from '@tanstack/react-query'
import { api } from '../services/api'

export interface IntakePayload {
  applicant_email: string
  organization_name?: string
  project_title: string
  country?: string
  sector?: string
  proposed_methodology?: string
}

export interface IntakeResponse {
  id: string
  applicant_token: string
  project_title: string
  status: string
}

export function useSubmitApplication() {
  return useMutation<IntakeResponse, Error, IntakePayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/applications', payload)
      return res.data as IntakeResponse
    },
  })
}
