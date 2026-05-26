import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export interface Token {
  id: string
  project: string
  tonnes: number
  vintage: number
  methodology: string
  vvb: string
  price: number | null
  status: 'listed' | 'minted' | 'retired'
  radixAddress: string
}

export interface MarketplaceListing {
  id: string
  token_id: string
  project: string
  tonnes: number
  vintage: number
  methodology: string
  vvb: string
  price: number
  radixAddress: string
}

export interface MintPayload {
  project: string
  tonnes: number
  vintage: number
  methodology: string
  vvb: string
  certificate_id?: string
  calculation_run_id?: string
}

export interface RetirePayload {
  tonnes: number
  purpose: string
  beneficiary: string
  location: string
}

export function useTokens() {
  return useQuery<Token[]>({
    queryKey: ['tokens'],
    queryFn: async () => {
      const res = await api.get('/tokenization/tokens')
      return res.data as Token[]
    },
  })
}

export function useMarketplace() {
  return useQuery<MarketplaceListing[]>({
    queryKey: ['marketplace'],
    queryFn: async () => {
      const res = await api.get('/tokenization/marketplace')
      return res.data as MarketplaceListing[]
    },
  })
}

export function useMintToken() {
  const qc = useQueryClient()
  return useMutation<Token, Error, MintPayload>({
    mutationFn: async (payload) => {
      const res = await api.post('/tokenization/tokens/mint', payload)
      return res.data as Token
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })
}

export function useBuyToken() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, string>({
    mutationFn: async (listingId) => {
      const res = await api.post(`/tokenization/marketplace/${listingId}/buy`)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })
}

export function useRetireToken() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, { tokenId: string; payload: RetirePayload }>({
    mutationFn: async ({ tokenId, payload }) => {
      const res = await api.post(`/tokenization/tokens/${tokenId}/retire`, payload)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })
}
