import { useState } from 'react'
import { TrendingUp, ShoppingCart, Package, DollarSign, Calendar, MapPin, Leaf, Plus, X, Check, Loader2 } from 'lucide-react'
import {
  useBrokerageListings,
  useBrokerageTransactions,
  useCreateBrokerageListing,
  useCreateBrokerageTransaction,
  useMatchListing,
} from '../hooks/useBrokerage'

interface ListingFormState {
  project: string
  available: string
  price: string
  vintage: string
  methodology: string
  delivery: string
  location: string
}

export function BrokeragePage() {
  const [tab, setTab] = useState<'marketplace' | 'transactions' | 'list'>('marketplace')
  const [toast, setToast] = useState<string | null>(null)
  const [listingForm, setListingForm] = useState<ListingFormState>({
    project: '', available: '', price: '', vintage: '', methodology: 'TPDDTEC_v4', delivery: '30', location: '',
  })

  const { data: listings, isLoading: listingsLoading, isError: listingsError, error: listingsErrorObj } = useBrokerageListings()
  const { data: transactions, isLoading: txLoading, isError: txError, error: txErrorObj } = useBrokerageTransactions()
  const createListing = useCreateBrokerageListing()
  const createTransaction = useCreateBrokerageTransaction()
  const matchListing = useMatchListing()

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  const handleCreateListing = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createListing.mutateAsync({
        project: listingForm.project || 'New Project',
        methodology: listingForm.methodology,
        vintage: parseInt(listingForm.vintage) || 2024,
        available: parseInt(listingForm.available) || 0,
        price: parseFloat(listingForm.price) || 0,
        location: listingForm.location || 'Unknown',
        delivery: parseInt(listingForm.delivery) || 30,
        coBenefits: ['health'],
      })
      setListingForm({ project: '', available: '', price: '', vintage: '', methodology: 'TPDDTEC_v4', delivery: '30', location: '' })
      setTab('marketplace')
      showToast('Listing created successfully!')
    } catch (err: any) {
      showToast(err?.response?.data?.detail || err?.message || 'Failed to create listing')
    }
  }

  const handleBuy = async (listing: { id: string; project: string; available: number; price: number }) => {
    try {
      await createTransaction.mutateAsync({
        listing_id: listing.id,
        credits: listing.available,
        type: 'spot',
      })
      showToast(`Purchase confirmed for ${listing.project}`)
    } catch (err: any) {
      showToast(err?.response?.data?.detail || err?.message || 'Failed to create transaction')
    }
  }

  const handleMatch = async (listingId: string, projectName: string) => {
    try {
      const data = await matchListing.mutateAsync(listingId)
      showToast(data.message || `Matching engine searching buyers for ${projectName}`)
    } catch (err: any) {
      showToast(err?.response?.data?.detail || err?.message || 'Matching failed')
    }
  }

  const tabItems = [
    { key: 'marketplace' as const, label: 'Marketplace', icon: ShoppingCart },
    { key: 'transactions' as const, label: 'My Transactions', icon: Package },
    { key: 'list' as const, label: 'List Credits', icon: DollarSign },
  ]

  return (
    <div className="space-y-6 relative">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl bg-surface-900 text-white px-4 py-3 shadow-lg animate-slide-up">
          <Check className="h-4 w-4 text-primary-400" />
          <span className="text-sm">{toast}</span>
          <button onClick={() => setToast(null)} className="ml-2 text-surface-400 hover:text-white"><X className="h-3.5 w-3.5" /></button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-950/30 flex items-center justify-center">
          <TrendingUp className="w-5 h-5 text-primary-600 dark:text-primary-400" />
        </div>
        <div>
          <h2 className="page-title">Carbon Credit Brokerage</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500">Trade verified carbon credits</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-surface-100/80 dark:bg-surface-800/50 p-1">
        {tabItems.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
              tab === t.key
                ? 'bg-white dark:bg-surface-700 text-primary-700 dark:text-primary-300 shadow-sm'
                : 'text-surface-500 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200'
            }`}
          >
            <t.icon className="h-4 w-4" />
            <span className="hidden sm:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {tab === 'marketplace' && (
        <>
          {listingsError ? (
            <div className="card p-8 text-center">
              <p className="text-red-600 dark:text-red-400 font-medium">Failed to load listings</p>
              <p className="text-sm text-surface-500 mt-2">{(listingsErrorObj as any)?.response?.data?.detail || (listingsErrorObj as Error)?.message || 'Unknown error'}</p>
            </div>
          ) : listingsLoading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="relative">
                <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {(listings ?? []).map((listing) => (
                <div key={listing.id} className="card-hover p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-surface-900 dark:text-surface-100">{listing.project}</h3>
                      <div className="flex items-center gap-1.5 text-xs text-surface-400 dark:text-surface-500 mt-1">
                        <MapPin className="h-3 w-3" />
                        {listing.seller} · {listing.location}
                      </div>
                    </div>
                    <span className="badge badge-blue text-[10px]">
                      {listing.methodology}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                      <p className="text-lg font-bold text-surface-900 dark:text-surface-100">${listing.price}</p>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">per tonne</p>
                    </div>
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                      <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{listing.available.toLocaleString()}</p>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">available</p>
                    </div>
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                      <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{listing.vintage}</p>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">vintage</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {listing.coBenefits.map((cb) => (
                      <span key={cb} className="inline-flex items-center gap-1 rounded-full bg-primary-50 dark:bg-primary-950/30 px-2.5 py-1 text-[10px] font-medium text-primary-700 dark:text-primary-300 capitalize">
                        <Leaf className="h-3 w-3" />
                        {cb}
                      </span>
                    ))}
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 dark:bg-blue-950/30 px-2.5 py-1 text-[10px] font-medium text-blue-700 dark:text-blue-300">
                      <Calendar className="h-3 w-3" /> {listing.delivery} days
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleBuy(listing)}
                      disabled={createTransaction.isPending}
                      className="btn-primary flex-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {createTransaction.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Buy Now'}
                    </button>
                    <button
                      onClick={() => handleMatch(listing.id, listing.project)}
                      className="btn-secondary text-sm"
                    >
                      Match
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'transactions' && (
        <>
          {txError ? (
            <div className="card p-8 text-center">
              <p className="text-red-600 dark:text-red-400 font-medium">Failed to load transactions</p>
              <p className="text-sm text-surface-500 mt-2">{(txErrorObj as any)?.response?.data?.detail || (txErrorObj as Error)?.message || 'Unknown error'}</p>
            </div>
          ) : txLoading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="relative">
                <div className="h-10 w-10 rounded-full border-[3px] border-surface-200 border-t-primary-500 animate-spin" />
              </div>
            </div>
          ) : (
            <div className="card overflow-hidden">
              <div className="px-6 py-4 border-b border-surface-200/60 dark:border-surface-800/40">
                <h3 className="font-semibold text-surface-900 dark:text-surface-100">Transaction History</h3>
              </div>
              <div className="divide-y divide-surface-100/60 dark:divide-surface-800/40">
                {(transactions ?? []).map((tx) => (
                  <div key={tx.id} className="flex items-center justify-between px-6 py-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-surface-900 dark:text-surface-100">{tx.id}</span>
                        <span className={`badge text-[10px] ${
                          tx.status === 'completed' ? 'badge-green' :
                          tx.status === 'in_escrow' ? 'badge-amber' :
                          'badge-blue'
                        }`}>
                          {(tx.status || '').replace('_', ' ')}
                        </span>
                        <span className="rounded-md bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5 text-[10px] text-surface-500 dark:text-surface-400 uppercase">
                          {tx.type}
                        </span>
                      </div>
                      <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">
                        {tx.credits.toLocaleString()} credits @ ${tx.price} · Total: ${tx.total.toLocaleString()}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-surface-400 dark:text-surface-500">Commission: ${tx.commission.toFixed(2)}</p>
                      <p className="text-[10px] text-surface-300 dark:text-surface-600">{tx.date}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'list' && (
        <form onSubmit={handleCreateListing} className="mx-auto max-w-2xl card p-6 space-y-5">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">List Credits for Sale</h3>
          {createListing.isError && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/20 p-3 text-sm text-red-600 dark:text-red-400">
              {(createListing.error as any)?.response?.data?.detail || (createListing.error as Error)?.message || 'Failed to create listing'}
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project</label>
              <input value={listingForm.project} onChange={(e) => setListingForm({ ...listingForm, project: e.target.value })} className="input-modern" placeholder="Project name" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Methodology</label>
              <select value={listingForm.methodology} onChange={(e) => setListingForm({ ...listingForm, methodology: e.target.value })} className="input-modern">
                <option value="TPDDTEC_v4">TPDDTEC v4</option>
                <option value="VM0050">VM0050</option>
                <option value="VMR0006">VMR0006</option>
                <option value="AMS-II.G">AMS-II.G</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Available Credits</label>
              <input type="number" value={listingForm.available} onChange={(e) => setListingForm({ ...listingForm, available: e.target.value })} className="input-modern" placeholder="5000" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Price per Credit (USD)</label>
              <input type="number" step="0.01" value={listingForm.price} onChange={(e) => setListingForm({ ...listingForm, price: e.target.value })} className="input-modern" placeholder="12.50" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Vintage Year</label>
              <input type="number" value={listingForm.vintage} onChange={(e) => setListingForm({ ...listingForm, vintage: e.target.value })} className="input-modern" placeholder="2024" required />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Delivery (days)</label>
              <input type="number" value={listingForm.delivery} onChange={(e) => setListingForm({ ...listingForm, delivery: e.target.value })} className="input-modern" placeholder="30" />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Location</label>
              <input value={listingForm.location} onChange={(e) => setListingForm({ ...listingForm, location: e.target.value })} className="input-modern" placeholder="Country / Region" />
            </div>
          </div>
          <button type="submit" disabled={createListing.isPending} className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed">
            {createListing.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            {createListing.isPending ? ' Creating…' : ' Create Listing'}
          </button>
          <p className="text-center text-xs text-surface-400 dark:text-surface-500">
            Commission: 2.5% auto-deducted on successful transaction
          </p>
        </form>
      )}
    </div>
  )
}
