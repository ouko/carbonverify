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
  project: string
  methodology: string
  vintage: number
  available: number
  price: number
  location: string
  delivery: number
  coBenefits?: string[]
}

export interface CreateTransactionPayload {
  listing_id: string
  credits: number
  type: 'spot' | 'forward' | 'escrow'
}

export interface MatchResponse {
  match_id: string
  status: string
  message: string
}

export function useBrokerageListings() {
  return useQuery<BrokerageListing[]>({
    queryKey: ['brokerage', 'listings'],
    queryFn: async () => {
      const res = await api.get('/brokerage/listings')
      return res.data as BrokerageListing[]
    },
  })
}

export function useBrokerageTransactions() {
  return useQuery<BrokerageTransaction[]>({
    queryKey: ['brokerage', 'transactions'],
    queryFn: async () => {
      const res = await api.get('/brokerage/transactions')
      return res.data as BrokerageTransaction[]
    },
  })
}

export function useCreateBrokerageListing() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateListingPayload) => {
      const res = await api.post('/brokerage/listings', payload)
      return res.data as BrokerageListing
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}

export function useCreateBrokerageTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateTransactionPayload) => {
      const res = await api.post('/brokerage/transactions', payload)
      return res.data as BrokerageTransaction
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
      const res = await api.post(`/brokerage/match/listing/${listingId}`)
      return res.data as MatchResponse
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}

export function useRunGlobalMatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await api.post('/brokerage/match/run-global')
      return res.data as MatchResponse
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['brokerage', 'listings'] }),
  })
}
