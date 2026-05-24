import { useState } from 'react'
import { Clock, AlertTriangle, Send, FileText, XCircle } from 'lucide-react'
import { useVVBPipeline } from '../../hooks/useCommandData'

const STAGES = [
  { id: 'draft', label: 'Draft', color: 'bg-gray-100 dark:bg-gray-700' },
  { id: 'submitted', label: 'Submitted', color: 'bg-blue-100 dark:bg-blue-900/30' },
  { id: 'under_review', label: 'Under Review', color: 'bg-indigo-100 dark:bg-indigo-900/30' },
  { id: 'clarification_requested', label: 'Clarification', color: 'bg-yellow-100 dark:bg-yellow-900/30' },
  { id: 'approved', label: 'Approved', color: 'bg-green-100 dark:bg-green-900/30' },
  { id: 'rejected', label: 'Rejected', color: 'bg-red-100 dark:bg-red-900/30' },
]

export function VVBPipelinePage() {
  const { data: pipeline, isLoading } = useVVBPipeline()
  const [selectedCard, setSelectedCard] = useState<any>(null)
  const [draftResponse, setDraftResponse] = useState('')

  const getDeadlineBadge = (card: any) => {
    if (card.overdue) return <span className="inline-flex animate-pulse items-center gap-1 rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white"><AlertTriangle className="h-3 w-3" />OVERDUE</span>
    if (card.deadlineWarning) return <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold text-orange-800 dark:bg-orange-900/30 dark:text-orange-300"><Clock className="h-3 w-3" />&lt;7d</span>
    return <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600 dark:bg-gray-700 dark:text-gray-300"><Clock className="h-3 w-3" />{card.daysInStage}d</span>
  }

  const handleDraftResponse = (card: any) => {
    setSelectedCard(card)
    setDraftResponse(`Dear VVB Reviewer,\n\nThank you for your query regarding ${card.projectName}.\n\nRegarding your question about ${card.clarificationQuery}:\n\n[Auto-drafted response based on project data and methodology KB]\n\nPlease let us know if you require any further information.\n\nBest regards,\nCarbonVerify Operations Team`)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-white">VVB Pipeline</h2>
        <div className="flex gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-600 animate-pulse" /> Overdue</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-orange-500" /> &lt; 7 days</span>
        </div>
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-gray-500">Loading pipeline...</div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {STAGES.map((stage) => {
            const cards = (pipeline || {})[stage.id] || []
            return (
              <div key={stage.id} className="flex w-72 min-w-[18rem] flex-col">
                <div className={`mb-2 rounded-lg px-3 py-2 ${stage.color}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-700 dark:text-gray-200">{stage.label}</span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs font-bold text-gray-600 shadow-sm dark:bg-gray-800 dark:text-gray-300">{cards.length}</span>
                  </div>
                </div>
                <div className="flex flex-1 flex-col gap-2">
                  {cards.map((card: any) => (
                    <div
                      key={card.id}
                      onClick={() => setSelectedCard(card)}
                      className={`cursor-pointer rounded-lg border p-3 transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800 ${
                        card.overdue ? 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/20' : 'border-gray-200 bg-white'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <p className="text-xs font-medium text-gray-900 dark:text-white line-clamp-1">{card.projectName}</p>
                        {getDeadlineBadge(card)}
                      </div>
                      <div className="mt-1.5 flex items-center gap-2 text-[10px] text-gray-500 dark:text-gray-400">
                        <span className="rounded bg-gray-100 px-1 py-0.5 dark:bg-gray-700">{card.methodology}</span>
                        <span className="rounded bg-gray-100 px-1 py-0.5 dark:bg-gray-700">{card.registry}</span>
                      </div>
                      {card.clarificationQuery && (
                        <div className="mt-2 rounded bg-yellow-50 p-2 text-[10px] text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                          <p className="font-medium">Query:</p>
                          <p className="line-clamp-2">{card.clarificationQuery}</p>
                        </div>
                      )}
                      {card.stage === 'clarification_requested' && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDraftResponse(card) }}
                          className="mt-2 flex w-full items-center justify-center gap-1 rounded bg-indigo-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-indigo-700"
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

      {/* Draft Response Modal */}
      {selectedCard && selectedCard.clarificationQuery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Draft VVB Response — {selectedCard.projectName}</h3>
              <button onClick={() => setSelectedCard(null)} className="text-gray-400 hover:text-gray-600">
                <XCircle className="h-5 w-5" />
              </button>
            </div>
            <div className="mb-3 rounded-lg bg-yellow-50 p-3 text-sm text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
              <p className="font-medium">VVB Query:</p>
              <p>{selectedCard.clarificationQuery}</p>
            </div>
            <textarea
              value={draftResponse}
              onChange={(e) => setDraftResponse(e.target.value)}
              rows={10}
              className="w-full rounded-lg border border-gray-300 p-3 text-sm font-mono text-gray-700 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setSelectedCard(null)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700">Cancel</button>
              <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"><Send className="mr-1 inline h-4 w-4" /> Submit Response</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
