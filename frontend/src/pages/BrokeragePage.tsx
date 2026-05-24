import { useState } from 'react'
import { TrendingUp, ShoppingCart, Package, DollarSign, Calendar } from 'lucide-react'

const MOCK_LISTINGS = [
  { id: 'L-001', project: 'Kenya Clean Cookstoves', methodology: 'TPDDTEC v4', vintage: 2024, available: 5000, price: 12.50, location: 'Kenya', delivery: 30, coBenefits: ['health', 'gender'], seller: 'EcoDev Ltd' },
  { id: 'L-002', project: 'Ghana Biogas Program', methodology: 'VM0050', vintage: 2023, available: 12000, price: 18.00, location: 'Ghana', delivery: 45, coBenefits: ['energy', 'waste'], seller: 'GreenFuel GH' },
  { id: 'L-003', project: 'Ethiopia LPG Adoption', methodology: 'AMS-II.G', vintage: 2024, available: 3000, price: 9.75, location: 'Ethiopia', delivery: 21, coBenefits: ['health', 'forest'], seller: 'EthioCarbon' },
  { id: 'L-004', project: 'Nepal Improved Charcoal', methodology: 'TPDDTEC v4', vintage: 2023, available: 8500, price: 14.20, location: 'Nepal', delivery: 60, coBenefits: ['forest', 'biodiversity'], seller: 'Himalaya Green' },
]

const MOCK_TRANSACTIONS = [
  { id: 'TX-001', type: 'spot', listing: 'L-001', credits: 1000, price: 12.50, total: 12500, commission: 312.50, status: 'completed', date: '2024-06-10' },
  { id: 'TX-002', type: 'forward', listing: 'L-002', credits: 5000, price: 17.50, total: 87500, commission: 2187.50, status: 'confirmed', date: '2024-06-12', delivery: '2024-09-01' },
  { id: 'TX-003', type: 'escrow', listing: 'L-003', credits: 500, price: 9.75, total: 4875, commission: 121.88, status: 'in_escrow', date: '2024-06-14' },
]

export function BrokeragePage() {
  const [tab, setTab] = useState<'marketplace' | 'transactions' | 'list'>('marketplace')
  const [listingForm, setListingForm] = useState({
    project: '', available: '', price: '', vintage: '', methodology: 'TPDDTEC_v4', delivery: '30', location: '',
  })

  const handleCreateListing = (e: React.FormEvent) => {
    e.preventDefault()
    alert('Listing created! (demo)')
  }

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
        <TrendingUp className="h-6 w-6 text-indigo-600" /> Carbon Credit Brokerage
      </h1>

      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {[
          { key: 'marketplace', label: 'Marketplace', icon: ShoppingCart },
          { key: 'transactions', label: 'My Transactions', icon: Package },
          { key: 'list', label: 'List Credits', icon: DollarSign },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-white text-indigo-700 shadow-sm dark:bg-gray-700 dark:text-indigo-300'
                : 'text-gray-600 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-gray-700'
            }`}
          >
            <t.icon className="h-4 w-4" />
            <span className="hidden sm:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {tab === 'marketplace' && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {MOCK_LISTINGS.map((listing) => (
            <div key={listing.id} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{listing.project}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{listing.seller} · {listing.location}</p>
                </div>
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300">
                  {listing.methodology}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div className="rounded bg-gray-50 p-2 dark:bg-gray-700">
                  <p className="text-lg font-bold text-gray-900 dark:text-white">${listing.price}</p>
                  <p className="text-[10px] text-gray-500">per tonne</p>
                </div>
                <div className="rounded bg-gray-50 p-2 dark:bg-gray-700">
                  <p className="text-lg font-bold text-gray-900 dark:text-white">{listing.available.toLocaleString()}</p>
                  <p className="text-[10px] text-gray-500">available</p>
                </div>
                <div className="rounded bg-gray-50 p-2 dark:bg-gray-700">
                  <p className="text-lg font-bold text-gray-900 dark:text-white">{listing.vintage}</p>
                  <p className="text-[10px] text-gray-500">vintage</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {listing.coBenefits.map((cb) => (
                  <span key={cb} className="rounded bg-green-50 px-2 py-0.5 text-[10px] text-green-700 dark:bg-green-900/20 dark:text-green-300">
                    {cb}
                  </span>
                ))}
                <span className="flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 text-[10px] text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
                  <Calendar className="h-3 w-3" /> {listing.delivery} days delivery
                </span>
              </div>
              <div className="mt-3 flex gap-2">
                <button className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                  Buy Now
                </button>
                <button className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">
                  Match
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'transactions' && (
        <div className="rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white">Transaction History</h3>
          </div>
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {MOCK_TRANSACTIONS.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{tx.id}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      tx.status === 'completed' ? 'bg-green-100 text-green-800 dark:bg-green-900/30' :
                      tx.status === 'in_escrow' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30' :
                      'bg-blue-100 text-blue-800 dark:bg-blue-900/30'
                    }`}>
                      {tx.status}
                    </span>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                      {tx.type}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {tx.credits.toLocaleString()} credits @ ${tx.price} · Total: ${tx.total.toLocaleString()}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-500 dark:text-gray-400">Commission: ${tx.commission.toFixed(2)}</p>
                  <p className="text-xs text-gray-400">{tx.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'list' && (
        <form onSubmit={handleCreateListing} className="mx-auto max-w-2xl space-y-4 rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white">List Credits for Sale</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Project</label>
              <input value={listingForm.project} onChange={(e) => setListingForm({ ...listingForm, project: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="Project name" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Methodology</label>
              <select value={listingForm.methodology} onChange={(e) => setListingForm({ ...listingForm, methodology: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                <option value="TPDDTEC_v4">TPDDTEC v4</option>
                <option value="VM0050">VM0050</option>
                <option value="VMR0006">VMR0006</option>
                <option value="AMS-II.G">AMS-II.G</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Available Credits</label>
              <input type="number" value={listingForm.available} onChange={(e) => setListingForm({ ...listingForm, available: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="5000" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Price per Credit (USD)</label>
              <input type="number" step="0.01" value={listingForm.price} onChange={(e) => setListingForm({ ...listingForm, price: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="12.50" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Vintage Year</label>
              <input type="number" value={listingForm.vintage} onChange={(e) => setListingForm({ ...listingForm, vintage: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="2024" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Delivery Timeline (days)</label>
              <input type="number" value={listingForm.delivery} onChange={(e) => setListingForm({ ...listingForm, delivery: e.target.value })} className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="30" />
            </div>
          </div>
          <button type="submit" className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-700">
            Create Listing
          </button>
          <p className="text-center text-xs text-gray-500 dark:text-gray-400">
            Commission: 2.5% auto-deducted on successful transaction
          </p>
        </form>
      )}
    </div>
  )
}
