import { useState, useEffect, useCallback } from 'react'
import { Coins, Flame, ShoppingBag, Layers, Shield, ExternalLink, X, Check, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react'
import { useTokens, useMarketplace, useMintToken, useBuyToken, useRetireToken } from '../hooks/useTokenization'
import type { Token, MarketplaceListing } from '../hooks/useTokenization'
import { useCalculations, useCalculation } from '../hooks/useCalculations'
import { useProjects } from '../hooks/useProjects'

type SelectableToken = Token | MarketplaceListing

function ProvenanceModal({ token, onClose }: { token: SelectableToken; onClose: () => void }) {
  const isToken = !('token_id' in token)
  const calcId = isToken ? (token as Token).calculationRunId : null
  const { data: calc } = useCalculation(calcId || '')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
      <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Token Provenance</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3 text-sm">
          {[
            { label: 'Token ID', value: ('token_id' in token ? token.token_id : token.id), mono: true },
            { label: 'Project', value: token.project },
            { label: 'Tonnes CO₂e', value: token.tonnes.toLocaleString() },
            { label: 'Vintage', value: token.vintage },
            { label: 'Methodology', value: token.methodology },
            { label: 'VVB', value: token.vvb },
            { label: 'Radix Address', value: token.radixAddress ?? '—', mono: true, small: true },
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
            {calc ? (
              <p className="text-xs text-surface-500 dark:text-surface-400">
                fNRB: {calc.fNRB_value ?? 'N/A'} · Emissions reduction: {calc.emissions_reduction_tCO2e?.toLocaleString() ?? 'N/A'} tCO₂e · Uncertainty: ±{calc.uncertainty_95CI ? Math.round(calc.uncertainty_95CI * 100) : 'N/A'}%
              </p>
            ) : (
              <p className="text-xs text-surface-400 dark:text-surface-500">
                {calcId ? 'Loading calculation data...' : 'No calculation run linked to this token.'}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="mt-5 w-full btn-secondary"
        >
          Close
        </button>
      </div>
    </div>
  )
}

export function TokenizationPage() {
  const [tab, setTab] = useState<'marketplace' | 'mint' | 'retire'>('marketplace')
  const [selectedToken, setSelectedToken] = useState<SelectableToken | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const perPage = 6

  useEffect(() => {
    setPage(1)
  }, [tab])

  const [mintForm, setMintForm] = useState({
    project_id: '',
    tonnes: '',
    vintage: '2024',
    methodology: 'TPDDTEC_v4',
    vvb: 'Verra',
    certificateId: '',
    calculationRunId: '',
  })

  const [retireForm, setRetireForm] = useState({
    tokenId: '',
    tonnes: '',
    purpose: '',
    beneficiary: '',
    location: '',
  })

  const { data: tokens, isLoading: tokensLoading, isError: tokensError } = useTokens()
  const { data: listings, isLoading: listingsLoading, isError: listingsError } = useMarketplace()
  const { data: calculations, isLoading: calcLoading, isError: calcError } = useCalculations()
  const { data: projects } = useProjects()

  const total = listings?.length ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const currentPage = Math.min(page, totalPages)
  const paginated = listings?.slice((currentPage - 1) * perPage, currentPage * perPage)

  const mintMutation = useMintToken()
  const buyMutation = useBuyToken()
  const retireMutation = useRetireToken()

  const showToast = useCallback((msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }, [])

  useEffect(() => {
    if (mintMutation.isError) {
      showToast((mintMutation.error as Error)?.message || 'Failed to mint token')
    }
  }, [mintMutation.isError, mintMutation.error, showToast])

  useEffect(() => {
    if (buyMutation.isError) {
      showToast((buyMutation.error as Error)?.message || 'Failed to buy token')
    }
  }, [buyMutation.isError, buyMutation.error, showToast])

  useEffect(() => {
    if (retireMutation.isError) {
      showToast((retireMutation.error as Error)?.message || 'Failed to retire token')
    }
  }, [retireMutation.isError, retireMutation.error, showToast])

  const handleMint = (e: React.FormEvent) => {
    e.preventDefault()
    if (!mintForm.project_id) {
      showToast('Please select a project')
      return
    }
    if (!mintForm.calculationRunId) {
      showToast('Please select a calculation run')
      return
    }
    mintMutation.mutate(
      {
        project_id: mintForm.project_id,
        tonnes_co2e: parseFloat(mintForm.tonnes) || 0,
        vintage_year: parseInt(mintForm.vintage) || 2024,
        methodology: mintForm.methodology,
        vvb_registry: mintForm.vvb,
        vvb_certificate_id: mintForm.certificateId || undefined,
        calculation_run_id: mintForm.calculationRunId,
      },
      {
        onSuccess: (data) => {
          setMintForm({
            project_id: '',
            tonnes: '',
            vintage: '2024',
            methodology: 'TPDDTEC_v4',
            vvb: 'Verra',
            certificateId: '',
            calculationRunId: '',
          })
          setTab('marketplace')
          showToast(`Minted ${(data.tonnes ?? 0).toLocaleString()} tCO₂e token on Radix`)
        },
      }
    )
  }

  const handleRetire = (e: React.FormEvent) => {
    e.preventDefault()
    if (!retireForm.tokenId) {
      showToast('Please select a token to retire')
      return
    }
    const retireTonnes = parseInt(retireForm.tonnes) || 0
    retireMutation.mutate(
      {
        token_id: retireForm.tokenId,
        tonnes_retired: retireTonnes,
        purpose: retireForm.purpose,
        beneficiary_name: retireForm.beneficiary,
        beneficiary_location: retireForm.location,
      },
      {
        onSuccess: () => {
          setRetireForm({ tokenId: '', tonnes: '', purpose: '', beneficiary: '', location: '' })
          setTab('marketplace')
          showToast(`Retired ${retireTonnes.toLocaleString()} tCO₂e — permanent burn recorded on Radix`)
        },
      }
    )
  }

  const handleBuy = (listingId: string, projectName: string) => {
    buyMutation.mutate({ listingId, tonnesToBuy: 1 }, {
      onSuccess: () => showToast(`Purchase request sent for ${projectName}`),
    })
  }

  const tabItems = [
    { key: 'marketplace' as const, label: 'Marketplace', icon: ShoppingBag },
    { key: 'mint' as const, label: 'Mint Token', icon: Layers },
    { key: 'retire' as const, label: 'Retire', icon: Flame },
  ]

  const retireOptions = (tokens || []).filter(
    (t) => t.status === 'minted' || (t.status === 'listed' && t.tonnes > 0)
  )

  const anyError = tokensError || listingsError || calcError

  return (
    <div className="space-y-6 relative">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl bg-surface-900 text-white px-4 py-3 shadow-lg animate-slide-up">
          {toast.includes('Failed') ? (
            <AlertTriangle className="h-4 w-4 text-red-400" />
          ) : (
            <Check className="h-4 w-4 text-primary-400" />
          )}
          <span className="text-sm">{toast}</span>
          <button onClick={() => setToast(null)} aria-label="Close" className="ml-2 text-surface-400 hover:text-white"><X className="h-3.5 w-3.5" /></button>
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

      {/* Error Banner */}
      {anyError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-950/20 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-700 dark:text-red-300">Failed to load data</p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-0.5">Please refresh the page or try again later.</p>
          </div>
        </div>
      )}

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
          {listingsLoading || tokensLoading ? (
            <div className="col-span-full card p-12 text-center">
              <p className="text-sm text-surface-500 dark:text-surface-400">Loading marketplace...</p>
            </div>
          ) : (
            <>
              {(paginated || []).map((listing) => (
                <div key={listing.id} className="card-hover p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="font-semibold text-surface-900 dark:text-surface-100">{listing.project}</h3>
                      <p className="text-xs text-surface-400 dark:text-surface-500 mt-1">{listing.vvb} verified · Vintage {listing.vintage}</p>
                    </div>
                    <span className="badge badge-blue text-[10px]">{listing.methodology}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                      <p className="text-lg font-bold text-surface-900 dark:text-surface-100">{listing.tonnes.toLocaleString()}</p>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">tonnes CO₂e</p>
                    </div>
                    <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3 text-center">
                      <p className="text-lg font-bold text-surface-900 dark:text-surface-100">${listing.price}</p>
                      <p className="text-[10px] text-surface-400 dark:text-surface-500 uppercase tracking-wider">per tonne</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-surface-400 dark:text-surface-500 mb-4">
                    <Shield className="h-3.5 w-3.5 text-primary-500" />
                    <span className="font-mono">{(listing.radixAddress ?? '—').slice(0, 20)}...</span>
                    {listing.radixAddress && (
                      <button
                        aria-label="Open external link"
                        onClick={() => window.open(`https://radixscan.io/account/${listing.radixAddress}`, '_blank')}
                        className="text-primary-600 hover:text-primary-500 dark:text-primary-400"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleBuy(listing.id, listing.project)}
                      disabled={buyMutation.isPending}
                      className="btn-primary flex-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {buyMutation.isPending ? 'Processing...' : 'Buy'}
                    </button>
                    <button onClick={() => setSelectedToken(listing)} className="btn-secondary text-sm">Details</button>
                  </div>
                </div>
              ))}
              {(paginated || []).length === 0 && !listingsLoading && (
                <div className="col-span-full card p-12 text-center">
                  <p className="text-sm text-surface-500 dark:text-surface-400">No tokens currently listed.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
      {tab === 'marketplace' && total > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-surface-500 dark:text-surface-400">
            Showing {(currentPage - 1) * perPage + 1}-{Math.min(currentPage * perPage, total)} of {total}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="btn-ghost text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {tab === 'mint' && (
        <form onSubmit={handleMint} className="mx-auto max-w-2xl card p-6 space-y-5">
          <h3 className="font-semibold text-surface-900 dark:text-surface-100">Mint New Carbon Credit Token</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Project</label>
                <select className="input-modern" value={mintForm.project_id} onChange={(e) => setMintForm({ ...mintForm, project_id: e.target.value })}>
                  <option value="">Select a project…</option>
                  {(projects ?? []).map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1.5">Calculation Run</label>
                <select
                  className="input-modern"
                  value={mintForm.calculationRunId}
                  onChange={(e) => setMintForm({ ...mintForm, calculationRunId: e.target.value })}
                  disabled={calcLoading}
                >
                  <option value="">{calcLoading ? 'Loading...' : 'Select a run'}</option>
                  {(calculations || []).map((run) => (
                    <option key={run.id} value={run.id}>
                      Run {run.id.slice(-6)} — {run.monitoring_period_start ?? '—'} to {run.monitoring_period_end ?? '—'}
                    </option>
                  ))}
                </select>
                {calcError && <p className="text-xs text-red-600 mt-1">Failed to load calculations</p>}
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
              <input className="input-modern" placeholder="VCU-1234-5678" value={mintForm.certificateId} onChange={(e) => setMintForm({ ...mintForm, certificateId: e.target.value })} />
            </div>
            <button type="submit" disabled={mintMutation.isPending} className="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed">
              <Layers className="w-4 h-4" /> {mintMutation.isPending ? 'Minting...' : 'Mint Token on Radix'}
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
              <select
                className="input-modern"
                value={retireForm.tokenId}
                onChange={(e) => setRetireForm({ ...retireForm, tokenId: e.target.value })}
                disabled={tokensLoading}
              >
                <option value="">{tokensLoading ? 'Loading...' : 'Select a token'}</option>
                {retireOptions.map((t) => (
                  <option key={t.id} value={t.id}>{t.id} — {t.project} ({t.tonnes.toLocaleString()} tonnes)</option>
                ))}
              </select>
              {tokensError && <p className="text-xs text-red-600 mt-1">Failed to load tokens</p>}
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
            <button type="submit" disabled={retireMutation.isPending} className="w-full rounded-xl bg-red-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-red-500 active:scale-[0.98] transition-all shadow-lg shadow-red-600/20 disabled:opacity-50 disabled:cursor-not-allowed">
              <Flame className="w-4 h-4 inline mr-1.5" /> {retireMutation.isPending ? 'Retiring...' : 'Retire Token Permanently'}
            </button>
          </div>
        </form>
      )}

      {selectedToken && (
        <ProvenanceModal token={selectedToken} onClose={() => setSelectedToken(null)} />
      )}
    </div>
  )
}
