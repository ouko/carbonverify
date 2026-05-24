import { useState } from 'react'
import { Coins, Flame, ShoppingBag, Layers, Shield, ExternalLink } from 'lucide-react'

const MOCK_TOKENS = [
  { id: 'T-001', project: 'Kenya Clean Cookstoves', tonnes: 5000, vintage: 2024, methodology: 'TPDDTEC v4', vvb: 'Verra', price: 13.00, status: 'listed', radixAddress: 'sim_token_abc123' },
  { id: 'T-002', project: 'Ghana Biogas Program', tonnes: 10000, vintage: 2023, methodology: 'VM0050', vvb: 'Gold Standard', price: 19.50, status: 'listed', radixAddress: 'sim_token_def456' },
  { id: 'T-003', project: 'Ethiopia LPG Adoption', tonnes: 2500, vintage: 2024, methodology: 'AMS-II.G', vvb: 'Verra', price: 10.25, status: 'minted', radixAddress: 'sim_token_ghi789' },
  { id: 'T-004', project: 'Nepal Improved Charcoal', tonnes: 3000, vintage: 2023, methodology: 'TPDDTEC v4', vvb: 'Kenya National', price: null, status: 'retired', radixAddress: 'sim_token_jkl012' },
]

export function TokenizationPage() {
  const [tab, setTab] = useState<'marketplace' | 'mint' | 'retire'>('marketplace')
  const [selectedToken, setSelectedToken] = useState<any>(null)

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
        <Coins className="h-6 w-6 text-indigo-600" /> Carbon Credit Tokenization
      </h1>

      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
        {[
          { key: 'marketplace', label: 'Marketplace', icon: ShoppingBag },
          { key: 'mint', label: 'Mint Token', icon: Layers },
          { key: 'retire', label: 'Retire', icon: Flame },
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
          {MOCK_TOKENS.filter((t) => t.status === 'listed').map((token) => (
            <div key={token.id} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{token.project}</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{token.vvb} verified · Vintage {token.vintage}</p>
                </div>
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300">
                  {token.methodology}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div className="rounded bg-gray-50 p-2 dark:bg-gray-700">
                  <p className="text-lg font-bold text-gray-900 dark:text-white">{token.tonnes.toLocaleString()}</p>
                  <p className="text-[10px] text-gray-500">tonnes CO₂e</p>
                </div>
                <div className="rounded bg-gray-50 p-2 dark:bg-gray-700">
                  <p className="text-lg font-bold text-gray-900 dark:text-white">${token.price}</p>
                  <p className="text-[10px] text-gray-500">per tonne</p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <Shield className="h-3.5 w-3.5" />
                <span className="font-mono">{token.radixAddress.slice(0, 20)}...</span>
                <button className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400">
                  <ExternalLink className="h-3 w-3" />
                </button>
              </div>
              <div className="mt-3 flex gap-2">
                <button className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700">
                  Buy
                </button>
                <button
                  onClick={() => setSelectedToken(token)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
                >
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'mint' && (
        <div className="mx-auto max-w-2xl space-y-4 rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white">Mint New Carbon Credit Token</h3>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Project</label>
                <select className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                  <option>Kenya Clean Cookstoves</option>
                  <option>Ghana Biogas Program</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Calculation Run</label>
                <select className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                  <option>Run #128 — June 2024</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Tonnes CO₂e</label>
                <input type="number" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="5000" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Vintage Year</label>
                <input type="number" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="2024" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Methodology</label>
                <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="TPDDTEC v4" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">VVB Registry</label>
                <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="Verra" />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">VVB Certificate ID</label>
              <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="VCU-1234-5678" />
            </div>
            <button className="w-full rounded-lg bg-indigo-600 py-2.5 text-sm font-medium text-white hover:bg-indigo-700">
              Mint Token on Radix
            </button>
          </div>
        </div>
      )}

      {tab === 'retire' && (
        <div className="mx-auto max-w-2xl space-y-4 rounded-lg border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
          <h3 className="font-semibold text-gray-900 dark:text-white">Retire Token (Permanent Burn)</h3>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Token to Retire</label>
              <select className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                <option>T-003 — Ethiopia LPG Adoption (2,500 tonnes)</option>
                <option>T-004 — Nepal Improved Charcoal (3,000 tonnes)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Tonnes to Retire</label>
              <input type="number" className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="1000" />
            </div>
            <div>
              <label className="text-xs text-gray-500 dark:text-gray-400">Purpose</label>
              <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="Scope 3 offset for FY2024" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Beneficiary Name</label>
                <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="Acme Corp" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400">Beneficiary Location</label>
                <input className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-700 dark:text-white" placeholder="Nairobi, Kenya" />
              </div>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-900/20">
              <p className="text-xs text-red-800 dark:text-red-300">
                <Flame className="inline h-3.5 w-3.5 mr-1" />
                Retirement is permanent. The token will be burned on the Radix ledger and cannot be reversed.
              </p>
            </div>
            <button className="w-full rounded-lg bg-red-600 py-2.5 text-sm font-medium text-white hover:bg-red-700">
              Retire Token Permanently
            </button>
          </div>
        </div>
      )}

      {selectedToken && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 dark:bg-gray-800">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Token Provenance</h3>
            <div className="mt-4 space-y-2 text-sm">
              <p><span className="text-gray-500">Token ID:</span> <span className="font-mono">{selectedToken.id}</span></p>
              <p><span className="text-gray-500">Project:</span> {selectedToken.project}</p>
              <p><span className="text-gray-500">Tonnes CO₂e:</span> {selectedToken.tonnes.toLocaleString()}</p>
              <p><span className="text-gray-500">Vintage:</span> {selectedToken.vintage}</p>
              <p><span className="text-gray-500">Methodology:</span> {selectedToken.methodology}</p>
              <p><span className="text-gray-500">VVB:</span> {selectedToken.vvb}</p>
              <p><span className="text-gray-500">Radix Address:</span> <span className="font-mono text-xs">{selectedToken.radixAddress}</span></p>
              <div className="mt-3 rounded bg-gray-50 p-3 dark:bg-gray-700">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300">MRV Data</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">fNRB: 0.42 · Emissions reduction: 12,450 tCO₂e · Uncertainty: ±8%</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedToken(null)}
              className="mt-4 w-full rounded-lg bg-gray-100 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
