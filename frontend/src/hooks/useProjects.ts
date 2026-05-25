import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { Project, ProjectCreate } from '../types'
import { mockProjects, addProject, getProjectById } from '../lib/mockData'

export function useProjects() {
  return useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: async () => mockProjects,
  })
}

export function useProject(id: string) {
  return useQuery<Project>({
    queryKey: ['projects', id],
    queryFn: async () => getProjectById(id),
    enabled: !!id,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ProjectCreate) => {
      const project = addProject(payload as Omit<Project, 'id' | 'created_at'>)
      return project
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}
