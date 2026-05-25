import { useState } from 'react'
import { Coins, Flame, ShoppingBag, Layers, Shield, ExternalLink, X, Check } from 'lucide-react'

interface Token {
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

const INITIAL_TOKENS: Token[] = [
  { id: 'T-001', project: 'Kenya Clean Cookstoves', tonnes: 5000, vintage: 2024, methodology: 'TPDDTEC v4', vvb: 'Verra', price: 13.00, status: 'listed', radixAddress: 'sim_token_abc123' },
  { id: 'T-002', project: 'Ghana Biogas Program', tonnes: 10000, vintage: 2023, methodology: 'VM0050', vvb: 'Gold Standard', price: 19.50, status: 'listed', radixAddress: 'sim_token_def456' },
  { id: 'T-003', project: 'Ethiopia LPG Adoption', tonnes: 2500, vintage: 2024, methodology: 'AMS-II.G', vvb: 'Verra', price: 10.25, status: 'minted', radixAddress: 'sim_token_ghi789' },
  { id: 'T-004', project: 'Nepal Improved Charcoal', tonnes: 3000, vintage: 2023, methodology: 'TPDDTEC v4', vvb: 'Kenya National', price: null, status: 'retired', radixAddress: 'sim_token_jkl012' },
]

let tokenCounter = 5

export function TokenizationPage() {
  const [tab, setTab] = useState<'marketplace' | 'mint' | 'retire'>('marketplace')
  const [tokens, setTokens] = useState<Token[]>(INITIAL_TOKENS)
  const [selectedToken, setSelectedToken] = useState<Token | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [mintForm, setMintForm] = useState({ project: 'Kenya Clean Cookstoves', tonnes: '', vintage: '2024', methodology: 'TPDDTEC v4', vvb: 'Verra' })
  const [retireForm, setRetireForm] = useState({ tokenId: 'T-003', tonnes: '', purpose: '', beneficiary: '', location: '' })

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  const handleMint = (e: React.FormEvent) => {
    e.preventDefault()
    const newToken: Token = {
      id: `T-00${tokenCounter++}`,
      project: mintForm.project,
      tonnes: parseInt(mintForm.tonnes) || 0,
      vintage: parseInt(mintForm.vintage) || 2024,
      methodology: mintForm.methodology,
      vvb: mintForm.vvb,
      price: null,
      status: 'minted',
      radixAddress: `sim_token_${Math.random().toString(36).slice(2, 8)}`,
    }
    setTokens((prev) => [newToken, ...prev])
    setMintForm({ project: 'Kenya Clean Cookstoves', tonnes: '', vintage: '2024', methodology: 'TPDDTEC v4', vvb: 'Verra' })
    setTab('marketplace')
    showToast(`Minted ${newToken.tonnes.toLocaleString()} tCO₂e token on Radix`)
  }

  const handleRetire = (e: React.FormEvent) => {
    e.preventDefault()
    const token = tokens.find((t) => t.id === retireForm.tokenId)
    if (!token) return
    const retireTonnes = parseInt(retireForm.tonnes) || 0
    if (retireTonnes >= token.tonnes) {
      setTokens((prev) => prev.map((t) => t.id === token.id ? { ...t, status: 'retired' as const, tonnes: 0, price: null } : t))
    } else {
      setTokens((prev) => prev.map((t) => t.id === token.id ? { ...t, tonnes: t.tonnes - retireTonnes } : t))
    }
    setRetireForm({ tokenId: 'T-003', tonnes: '', purpose: '', beneficiary: '', location: '' })
    setTab('marketplace')
    showToast(`Retired ${retireTonnes.toLocaleString()} tCO₂e — permanent burn recorded on Radix`)
  }

  const handleBuy = (token: Token) => {
    showToast(`Purchase request sent for ${token.project}`)
  }

  const tabItems = [
    { key: 'marketplace' as const, label: 'Marketplace', icon: ShoppingBag },
    { key: 'mint' as const, label: 'Mint Token', icon: Layers },
    { key: 'retire' as const, label: 'Retire', icon: Flame },
  ]

  const listedTokens = tokens.filter((t) => t.status === 'listed')
  const retireOptions = tokens.filter((t) => t.status === 'minted' || (t.status === 'listed' && t.tonnes > 0))

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
          <Coins className="w-5 h-5 text-primary-600 dark:text-primary-400" />
        </div>
        <div>
          <h2 className="page-title">Carbon Credit Tokenization</h2>
          <p className="text-sm text-surface-400 dark:text-surface-500">Mint and trade on Radix DLT</p>
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
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {listedTokens.map((token) => (
            <div key={token.id} className="card-hover p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-surface-900 dark:text-surface-100">{token.project}</h3>
                  <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">{token.vvb} verified · Vintage {token.vintage}</p>
                </div>
                <span className="badge badge-blue text-[10px]">{token.methodology}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 mb-4">
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                  <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{token.tonnes.toLocaleString()}</p>
                  <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">tonnes CO₂e</p>
                </div>
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                  <p className="text-lg font-bold text-surface-900 dark:text-surface-100">${token.price}</p>
                  <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">per tonne</p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-surface-400 dark:text-surface-500 mb-4">
                <Shield className="h-3.5 w-3.5 text-primary-500" />
                <span className="font-mono">{token.radixAddress.slice(0, 20)}...</span>
                <button className="text-primary-600 hover:text-primary-500 dark:text-primary-400">
                  <ExternalLink className="h-3 w-3" />
                </button>
              </div>
              <div className="flex gap-2">
                <button onClick={() => handleBuy(token)} className="btn-primary flex-1 text-sm">Buy</button>
                <button onClick={() => setSelectedToken(token)} className="btn-secondary text-sm">Details</button>
              </div>
            </div>
          ))}
          {listedTokens.length === 0 && (
            <div className="col-span-full card p-12 text-center">
              <p className="text-sm text-surface-500 dark:text-surface-400">No tokens currently listed.</p>
            </div>
          )}
        </div>
      )}

      {tab === 'mint' && (
        <form onSubmit={handleMint} className="mx-auto max-w-2xl card p-6 space-y-5">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">Mint New Carbon Credit Token</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project</label>
                <select className="input-modern" value={mintForm.project} onChange={(e) => setMintForm({ ...mintForm, project: e.target.value })}>
                  <option>Kenya Clean Cookstoves</option>
                  <option>Ghana Biogas Program</option>
                  <option>Ethiopia LPG Adoption</option>
                  <option>Nepal Improved Charcoal</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Calculation Run</label>
                <select className="input-modern">
                  <option>Run #128 — June 2024</option>
                  <option>Run #129 — March 2024</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Tonnes CO₂e</label>
                <input type="number" required className="input-modern" placeholder="5000" value={mintForm.tonnes} onChange={(e) => setMintForm({ ...mintForm, tonnes: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Vintage Year</label>
                <input type="number" className="input-modern" placeholder="2024" value={mintForm.vintage} onChange={(e) => setMintForm({ ...mintForm, vintage: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Methodology</label>
                <input className="input-modern" placeholder="TPDDTEC v4" value={mintForm.methodology} onChange={(e) => setMintForm({ ...mintForm, methodology: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">VVB Registry</label>
                <input className="input-modern" placeholder="Verra" value={mintForm.vvb} onChange={(e) => setMintForm({ ...mintForm, vvb: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">VVB Certificate ID</label>
              <input className="input-modern" placeholder="VCU-1234-5678" />
            </div>
            <button type="submit" className="btn-primary w-full">
              <Layers className="w-4 h-4" /> Mint Token on Radix
            </button>
          </div>
        </form>
      )}

      {tab === 'retire' && (
        <form onSubmit={handleRetire} className="mx-auto max-w-2xl card p-6 space-y-5">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">Retire Token (Permanent Burn)</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Token to Retire</label>
              <select className="input-modern" value={retireForm.tokenId} onChange={(e) => setRetireForm({ ...retireForm, tokenId: e.target.value })}>
                {retireOptions.map((t) => (
                  <option key={t.id} value={t.id}>{t.id} — {t.project} ({t.tonnes.toLocaleString()} tonnes)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Tonnes to Retire</label>
              <input type="number" required className="input-modern" placeholder="1000" value={retireForm.tonnes} onChange={(e) => setRetireForm({ ...retireForm, tonnes: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Purpose</label>
              <input className="input-modern" placeholder="Scope 3 offset for FY2024" value={retireForm.purpose} onChange={(e) => setRetireForm({ ...retireForm, purpose: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Beneficiary Name</label>
                <input className="input-modern" placeholder="Acme Corp" value={retireForm.beneficiary} onChange={(e) => setRetireForm({ ...retireForm, beneficiary: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Beneficiary Location</label>
                <input className="input-modern" placeholder="Nairobi, Kenya" value={retireForm.location} onChange={(e) => setRetireForm({ ...retireForm, location: e.target.value })} />
              </div>
            </div>
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-950/20">
              <p className="text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
                <Flame className="h-4 w-4 shrink-0 mt-0.5" />
                Retirement is permanent. The token will be burned on the Radix ledger and cannot be reversed.
              </p>
            </div>
            <button type="submit" className="w-full rounded-xl bg-red-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-red-500 active:scale-[0.98] transition-all shadow-lg shadow-red-600/20">
              <Flame className="w-4 h-4 inline mr-1.5" /> Retire Token Permanently
            </button>
          </div>
        </form>
      )}

      {selectedToken && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Token Provenance</h3>
              <button
                onClick={() => setSelectedToken(null)}
                className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              {[
                { label: 'Token ID', value: selectedToken.id, mono: true },
                { label: 'Project', value: selectedToken.project },
                { label: 'Tonnes CO₂e', value: selectedToken.tonnes.toLocaleString() },
                { label: 'Vintage', value: selectedToken.vintage },
                { label: 'Methodology', value: selectedToken.methodology },
                { label: 'VVB', value: selectedToken.vvb },
                { label: 'Radix Address', value: selectedToken.radixAddress, mono: true, small: true },
              ].map((field) => (
                <div key={field.label} className="flex justify-between items-center py-2 border-b border-surface-100 dark:border-surface-800/50 last:border-0">
                  <span className="text-surface-400 dark:text-surface-500">{field.label}</span>
                  <span className={field.mono ? 'font-mono text-xs' : 'font-medium text-surface-900 dark:text-surface-100'}>
                    {field.value}
                  </span>
                </div>
              ))}
              <div className="mt-3 rounded-xl bg-surface-50 dark:bg-surface-800/50 p-4">
                <p className="text-xs font-semibold text-surface-700 dark:text-surface-300 mb-1">MRV Data</p>
                <p className="text-xs text-surface-400 dark:text-surface-500">fNRB: 0.42 · Emissions reduction: 12,450 tCO₂e · Uncertainty: ±8%</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedToken(null)}
              className="mt-5 w-full btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
