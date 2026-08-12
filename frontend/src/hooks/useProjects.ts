import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { Project, ProjectCreate, ProjectPreAudit } from '../types'

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await api.get('/projects/')
      return res.data as Project[]
    },
  })
}

export function useProject(id: string) {
  return useQuery<Project>({
    queryKey: ['projects', id],
    queryFn: async () => {
      const res = await api.get(`/projects/${id}`)
      return res.data as Project
    },
    enabled: !!id,
  })
}

export function useProjectPreAudit(id: string) {
  return useQuery<ProjectPreAudit | null>({
    queryKey: ['projects', id, 'pre-audit'],
    queryFn: async () => {
      const res = await api.get(`/projects/${id}/pre-audit`)
      return res.data as ProjectPreAudit | null
    },
    enabled: !!id,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ProjectCreate) => {
      const res = await api.post('/projects/', payload)
      return res.data as Project
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}
