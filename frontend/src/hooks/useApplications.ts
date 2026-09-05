import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { api } from '../services/api'

// Dedicated client for applicant-token calls: no auth-store interceptor,
// so an explicit applicant bearer token is never overwritten.
const applicantApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 60000,
})

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

export interface PortalDocument {
  id: string
  original_filename?: string
  document_type?: string
  status: string
  created_at: string
}

export interface PortalData {
  application_id: string
  project_title: string
  status: string
  gap_findings: {
    required_document_types?: string[]
    classified_document_types?: string[]
    missing_document_types?: string[]
    has_gaps?: boolean
    remediation?: { document_type: string; guidance: string }[]
  }
  documents: PortalDocument[]
}

export function useSubmitApplication() {
  return useMutation<IntakeResponse, Error, IntakePayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/applications', payload)
      return res.data as IntakeResponse
    },
  })
}

export function useApplicantPortal(applicationId: string, token: string) {
  return useQuery<PortalData>({
    queryKey: ['applicant-portal', applicationId],
    queryFn: async () => {
      const res = await applicantApi.get(`/applications/${applicationId}/portal`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      return res.data as PortalData
    },
    enabled: !!applicationId && !!token,
    retry: false,
  })
}

export function useUploadApplicationDocument(applicationId: string, token: string) {
  const qc = useQueryClient()
  return useMutation<PortalDocument, Error, File>({
    mutationFn: async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await applicantApi.post(`/applications/${applicationId}/documents`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      })
      return res.data as PortalDocument
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applicant-portal', applicationId] }),
  })
}
