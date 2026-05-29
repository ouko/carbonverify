import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'

export interface BrokerageListing {
  id: string
  project: string
  methodology: string
  vintage: number
  available: number
  price: number
  location: string
  delivery: number
  coBenefits: string[]
  seller: string
}

export interface BrokerageTransaction {
  id: string
  type: 'spot' | 'forward' | 'escrow'
  listing: string
  credits: number
  price: number
  total: number
  commission: number
  status: 'completed' | 'confirmed' | 'in_escrow' | string
  date: string
  delivery?: string
}

export interface CreateListingPayload {
  project_id: string
  available_credits: number
  price_per_credit_usd: number
  vintage_year: number
  methodology: string
  location: string
  delivery_timeline_days: number
  co_benefits?: string[]
}

export interface CreateTransactionPayload {
  listing_id: string
  credits_amount: number
  trade_type: 'spot' | 'forward' | 'escrow'
}

export interface MatchResponse {
  listing_id: string
  matches: {
    buyer_id: string
    score: number
    methodology_match: boolean
    price_match: boolean
    location_match: boolean
    timeline_match: boolean
  }[]
}

export interface GlobalMatchResponse {
  listings_scanned: number
  buyers_scanned: number
  matches_created: number
}

// ─── Backend response shapes (snake_case) ───────────────────────────────────

interface BackendListing {
  id: string
  project_id: string
  seller_id: string
  available_credits: number
  price_per_credit_usd: number
  vintage_year: number
  methodology: string
  co_benefits: string[]
  delivery_timeline_days: number
  location: string | null
  status: string
  minimum_purchase: number
  created_at: string
}

interface BackendTransaction {
  id: string
  listing_id: string
  buyer_id: string
  seller_id: string
  trade_type: string
  credits_amount: number
  price_per_credit_usd: number
  total_value_usd: number
  commission_rate: number
  commission_usd: number
  status: string
  delivery_date: string | null
  created_at: string
}

function mapListing(item: BackendListing): BrokerageListing {
  return {
    id: item.id,
    project: item.project_id ?? 'Unknown Project',
    methodology: item.methodology ?? '',
    vintage: item.vintage_year ?? 0,
    available: item.available_credits ?? 0,
    price: item.price_per_credit_usd ?? 0,
    location: item.location ?? '',
    delivery: item.delivery_timeline_days ?? 30,
    coBenefits: item.co_benefits ?? [],
    seller: item.seller_id ?? 'Unknown Seller',
  }
}

function mapTransaction(item: BackendTransaction): BrokerageTransaction {
  return {
    id: item.id,
    type: item.trade_type as BrokerageTransaction['type'],
    listing: item.listing_id ?? '',
    credits: item.credits_amount ?? 0,
    price: item.price_per_credit_usd ?? 0,
    total: item.total_value_usd ?? 0,
    commission: item.commission_usd ?? 0,
    status: item.status ?? 'pending',
    date: item.created_at ?? '',
    delivery: item.delivery_date ?? undefined,
  }
}

// ─── Hooks ──────────────────────────────────────────────────────────────────

export function useBrokerageListings(skip = 0, limit = 50) {
  return useQuery<BrokerageListing[]>({
    queryKey: ['brokerage', 'listings', skip, limit],
    queryFn: async () => {
      const res = await api.get<BackendListing[]>(`/brokerage/listings?skip=${skip}&limit=${limit}`)
      return (res.data ?? []).map(mapListing)
    },
  })
}

export function useBrokerageTransactions(skip = 0, limit = 50) {
  return useQuery<BrokerageTransaction[]>({
    queryKey: ['brokerage', 'transactions', skip, limit],
    queryFn: async () => {
      const res = await api.get<BackendTransaction[]>(`/brokerage/transactions?skip=${skip}&limit=${limit}`)
      return (res.data ?? []).map(mapTransaction)
    },
  })
}

export function useCreateBrokerageListing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateListingPayload) => {
      const res = await api.post<BackendListing>('/brokerage/listings', payload)
      return mapListing(res.data)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}

export function useCreateBrokerageTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateTransactionPayload) => {
      const res = await api.post<BackendTransaction>('/brokerage/transactions', payload)
      return mapTransaction(res.data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['brokerage', 'transactions'] })
      qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] })
    },
  })
}

export function useMatchListing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (listingId: string) => {
      const res = await api.post<MatchResponse>(`/brokerage/match/listing/${listingId}`)
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}

export function useRunGlobalMatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<GlobalMatchResponse>('/brokerage/match/run-global')
      return res.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}
