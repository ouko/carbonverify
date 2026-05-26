import { useState } from 'react'
import { Clock, AlertTriangle, Send, FileText, X, CheckCircle, ArrowRight, GitPullRequest } from 'lucide-react'
import { useVVBPipeline } from '../../hooks/useCommandData'

const STAGES = [
  { id: 'draft', label: 'Draft', color: 'bg-surface-100 dark:bg-surface-800' },
  { id: 'submitted', label: 'Submitted', color: 'bg-blue-50 dark:bg-blue-950/20' },
  { id: 'under_review', label: 'Under Review', color: 'bg-violet-50 dark:bg-violet-950/20' },
  { id: 'clarification_requested', label: 'Clarification', color: 'bg-amber-50 dark:bg-amber-950/20' },
  { id: 'approved', label: 'Approved', color: 'bg-primary-50 dark:bg-primary-950/20' },
  { id: 'rejected', label: 'Rejected', color: 'bg-red-50 dark:bg-red-950/20' },
]

export function VVBPipelinePage() {
  const { data: pipeline, isLoading } = useVVBPipeline()
  const [selectedCard, setSelectedCard] = useState<any>(null)
  const [draftCard, setDraftCard] = useState<any>(null)
  const [draftResponse, setDraftResponse] = useState('')
  const [toast, setToast] = useState<string | null>(null)

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 2500)
  }

  const getDeadlineBadge = (card: any) => {
    if (card.overdue) return <span className="badge badge-red animate-pulse text-[10px]"><AlertTriangle className="h-3 w-3 mr-0.5" />OVERDUE</span>
    if (card.deadlineWarning) return <span className="badge bg-orange-50 text-orange-700 dark:bg-orange-950/20 dark:text-orange-300 text-[10px]"><Clock className="h-3 w-3 mr-0.5" />&lt;7d</span>
    return <span className="badge badge-slate text-[10px]"><Clock className="h-3 w-3 mr-0.5" />{card.daysInStage}d</span>
  }

  const openDetails = (card: any) => {
    setSelectedCard(card)
    setDraftCard(null)
  }

  const openDraftResponse = (card: any) => {
    setDraftCard(card)
    setDraftResponse(`Dear VVB Reviewer,\n\nThank you for your query regarding ${card.projectName}.\n\nRegarding your question about ${card.clarificationQuery}:\n\n[Auto-drafted response based on project data and methodology KB]\n\nPlease let us know if you require any further information.\n\nBest regards,\nCarbonVerify Operations Team`)
  }

  const handleSubmitResponse = () => {
    showToast(`Response submitted for ${draftCard?.projectName}`)
    setDraftCard(null)
  }

  const handleAdvanceStage = (card: any) => {
    const currentIdx = STAGES.findIndex((s) => s.id === card.stage)
    if (currentIdx >= 0 && currentIdx < STAGES.length - 1) {
      showToast(`Moved ${card.projectName} to ${STAGES[currentIdx + 1].label}`)
    }
    setSelectedCard(null)
  }

  return (
    <div className="space-y-4 relative">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-[60] flex items-center gap-2 rounded-xl bg-surface-900 text-white px-4 py-3 shadow-lg animate-slide-up">
          <CheckCircle className="h-4 w-4 text-primary-400" />
          <span className="text-sm">{toast}</span>
          <button onClick={() => setToast(null)} className="ml-2 text-surface-400 hover:text-white"><X className="h-3.5 w-3.5" /></button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-surface-900 dark:text-surface-100">VVB Pipeline</h2>
        <div className="flex gap-3 text-xs text-surface-400 dark:text-surface-500">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-600 animate-pulse" /> Overdue</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> &lt; 7 days</span>
        </div>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-surface-400">Loading pipeline...</div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map((stage) => {
            const cards = (pipeline || {})[stage.id] || []
            return (
              <div key={stage.id} className="flex w-72 min-w-[18rem] flex-col">
                <div className={`mb-2 rounded-xl px-3 py-2 ${stage.color}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-surface-700 dark:text-surface-200">{stage.label}</span>
                    <span className="rounded-full bg-white dark:bg-surface-800 px-2 py-0.5 text-xs font-bold text-surface-600 dark:text-surface-300 shadow-sm">{cards.length}</span>
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2">
                  {cards.map((card: any) => (
                    <div
                      key={card.id}
                      onClick={() => openDetails(card)}
                      className={`cursor-pointer rounded-xl border p-3 transition-all hover:shadow-soft ${
                        card.overdue ? 'border-red-200 bg-red-50 dark:border-red-900/30 dark:bg-red-950/10' : 'border-surface-200 dark:border-surface-700 bg-white dark:bg-surface-900'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <p className="text-xs font-semibold text-surface-900 dark:text-surface-100 line-clamp-1">{card.projectName}</p>
                        {getDeadlineBadge(card)}
                      </div>
                      <div className="mt-1.5 flex items-center gap-2 text-[10px] text-surface-400 dark:text-surface-500">
                        <span className="rounded-md bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5">{card.methodology}</span>
                        <span className="rounded-md bg-surface-100 dark:bg-surface-800 px-1.5 py-0.5">{card.registry}</span>
                      </div>
                      {card.clarificationQuery && (
                        <div className="mt-2 rounded-lg bg-amber-50 dark:bg-amber-950/10 p-2 text-[10px] text-amber-800 dark:text-amber-300">
                          <p className="font-semibold">Query:</p>
                          <p className="line-clamp-2">{card.clarificationQuery}</p>
                        </div>
                      )}
                      {card.stage === 'clarification_requested' && (
                        <button
                          onClick={(e) => { e.stopPropagation(); openDraftResponse(card) }}
                          className="mt-2 flex w-full items-center justify-center gap-1 rounded-xl bg-primary-600 px-2 py-1.5 text-[10px] font-medium text-white hover:bg-primary-500 active:scale-[0.98] transition-all"
                        >
                          <FileText className="h-3 w-3" /> Draft Response
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Card Details Modal */}
      {selectedCard && !draftCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitPullRequest className="h-5 w-5 text-primary-500" />
                <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">{selectedCard.projectName}</h3>
              </div>
              <button onClick={() => setSelectedCard(null)} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Stage</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100 capitalize">{(selectedCard.stage || '').replace('_', ' ')}</p>
                </div>
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Days in Stage</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{selectedCard.daysInStage} days</p>
                </div>
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Methodology</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{selectedCard.methodology}</p>
                </div>
                <div className="rounded-xl bg-surface-50 dark:bg-surface-800/50 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-surface-400 dark:text-surface-500 mb-1">Registry</p>
                  <p className="text-sm font-semibold text-surface-900 dark:text-surface-100">{selectedCard.registry}</p>
                </div>
              </div>

              {selectedCard.clarificationQuery && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/30 dark:bg-amber-950/10">
                  <p className="text-xs font-semibold text-amber-800 dark:text-amber-300 mb-1">VVB Clarification Query</p>
                  <p className="text-sm text-amber-700 dark:text-amber-400">{selectedCard.clarificationQuery}</p>
                  {selectedCard.draftResponse && (
                    <p className="mt-2 text-xs text-primary-600 dark:text-primary-400 flex items-center gap-1">
                      <FileText className="h-3 w-3" /> {selectedCard.draftResponse}
                    </p>
                  )}
                </div>
              )}

              {selectedCard.overdue && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900/30 dark:bg-red-950/10">
                  <p className="text-xs font-semibold text-red-800 dark:text-red-300 flex items-center gap-1.5">
                    <AlertTriangle className="h-4 w-4" /> This item is overdue — {selectedCard.daysInStage} days in stage
                  </p>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                {selectedCard.stage === 'clarification_requested' && (
                  <button onClick={() => openDraftResponse(selectedCard)} className="btn-primary flex-1 text-sm">
                    <FileText className="mr-1 inline h-4 w-4" /> Draft Response
                  </button>
                )}
                {selectedCard.stage !== 'approved' && selectedCard.stage !== 'rejected' && (
                  <button onClick={() => handleAdvanceStage(selectedCard)} className="btn-secondary flex-1 text-sm">
                    <ArrowRight className="mr-1 inline h-4 w-4" /> Advance Stage
                  </button>
                )}
                <button onClick={() => setSelectedCard(null)} className="btn-ghost text-sm">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Draft Response Modal */}
      {draftCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-950/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-700 p-6 shadow-soft-lg">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-surface-900 dark:text-surface-100">Draft VVB Response — {draftCard.projectName}</h3>
              <button onClick={() => setDraftCard(null)} className="p-1.5 rounded-lg text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mb-3 rounded-xl bg-amber-50 dark:bg-amber-950/10 p-3 text-sm text-amber-800 dark:text-amber-300">
              <p className="font-semibold">VVB Query:</p>
              <p>{draftCard.clarificationQuery}</p>
            </div>
            <textarea
              value={draftResponse}
              onChange={(e) => setDraftResponse(e.target.value)}
              rows={10}
              className="w-full rounded-xl border border-surface-200 dark:border-surface-700 p-3 text-sm font-mono text-surface-700 dark:bg-surface-950 dark:text-surface-200 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setDraftCard(null)} className="btn-secondary text-sm">Cancel</button>
              <button onClick={handleSubmitResponse} className="btn-primary text-sm"><Send className="mr-1 inline h-4 w-4" /> Submit Response</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
