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
  status: 'listed' | 'minted' | 'retired' | 'sold' | 'fractional'
  radixAddress: string | null
  calculationRunId: string | null
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
  radixAddress: string | null
}

export interface MintPayload {
  project_id: string
  calculation_run_id: string
  tonnes_co2e: number
  vintage_year: number
  methodology: string
  vvb_registry: string
  vvb_certificate_id?: string
}

export interface RetirePayload {
  token_id: string
  tonnes_retired: number
  purpose?: string
  beneficiary_name?: string
  beneficiary_location?: string
}

// ─── Backend shapes ──────────────────────────────────────────────────────────

interface BackendToken {
  id: string
  project_id: string
  calculation_run_id: string
  tonnes_co2e: number
  vintage_year: number
  methodology: string
  vvb_registry: string
  vvb_certificate_id: string | null
  radix_token_address: string | null
  status: string
  is_fractional: boolean
  parent_token_id: string | null
  created_at: string
}

interface BackendListing {
  id: string
  token_id: string
  seller_id: string
  price_per_tonne_usd: number
  amount_available: number
  status: string
  created_at: string
}

function mapToken(item: BackendToken): Token {
  return {
    id: item.id,
    project: item.project_id ?? 'Unknown',
    tonnes: item.tonnes_co2e ?? 0,
    vintage: item.vintage_year ?? 0,
    methodology: item.methodology ?? '',
    vvb: item.vvb_registry ?? '',
    price: null,
    status: item.status as Token['status'],
    radixAddress: item.radix_token_address ?? null,
    calculationRunId: item.calculation_run_id ?? null,
  }
}

function mapMarketplaceListing(item: BackendListing): MarketplaceListing {
  return {
    id: item.id,
    token_id: item.token_id ?? '',
    project: item.token_id ?? 'Unknown',
    tonnes: item.amount_available ?? 0,
    vintage: 0,
    methodology: '',
    vvb: '',
    price: item.price_per_tonne_usd ?? 0,
    radixAddress: null,
  }
}

// ─── Hooks ──────────────────────────────────────────────────────────────────

export function useTokens(skip = 0, limit = 50) {
  return useQuery<Token[]>({
    queryKey: ['tokens', skip, limit],
    queryFn: async () => {
      const res = await api.get<BackendToken[]>(`/tokenization/tokens?skip=${skip}&limit=${limit}`)
      return (res.data ?? []).map(mapToken)
    },
  })
}

export function useMarketplace(skip = 0, limit = 50) {
  return useQuery<MarketplaceListing[]>({
    queryKey: ['marketplace', skip, limit],
    queryFn: async () => {
      const res = await api.get<BackendListing[]>(`/tokenization/marketplace?skip=${skip}&limit=${limit}`)
      return (res.data ?? []).map(mapMarketplaceListing)
    },
  })
}

export function useMintToken() {
  const qc = useQueryClient()
  return useMutation<Token, Error, MintPayload>({
    mutationFn: async (payload) => {
      const res = await api.post<BackendToken>('/tokenization/tokens/mint', payload)
      return mapToken(res.data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })
}

export function useBuyToken() {
  const qc = useQueryClient()
  return useMutation<unknown, Error, { listingId: string; tonnesToBuy: number }>({
    mutationFn: async ({ listingId, tonnesToBuy }) => {
      const res = await api.post(`/tokenization/marketplace/${listingId}/buy?tonnes_to_buy=${tonnesToBuy}`)
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
  return useMutation<unknown, Error, RetirePayload>({
    mutationFn: async (payload) => {
      const res = await api.post(`/tokenization/tokens/${payload.token_id}/retire`, payload)
      return res.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] })
      qc.invalidateQueries({ queryKey: ['marketplace'] })
    },
  })
}
