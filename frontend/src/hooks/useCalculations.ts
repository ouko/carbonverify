import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import type { CalculationRun, CalculationRunCreate } from '../types'

export function useCalculations() {
  return useQuery<CalculationRun[]>({
    queryKey: ['calculations'],
    queryFn: async () => {
      const res = await api.get('/calculations/')
      return res.data as CalculationRun[]
    },
  })
}

export function useCalculation(id: string) {
  return useQuery<CalculationRun>({
    queryKey: ['calculations', id],
    queryFn: async () => {
      const res = await api.get(`/calculations/${id}`)
      return res.data as CalculationRun
    },
    enabled: !!id,
  })
}

export function useCreateCalculation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CalculationRunCreate) => {
      const res = await api.post('/calculations/', payload)
      return res.data as CalculationRun
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calculations'] }),
  })
}
