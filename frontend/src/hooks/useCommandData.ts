import { useQuery } from '@tanstack/react-query'

// Mock data generators for 200+ projects

function generateProjects(count: number) {
  const methodologies = ['TPDDTEC_v4', 'VM0050', 'VMR0006', 'AMS-II.G']
  const statuses = ['onboarding', 'data_collection', 'calculation', 'review', 'submitted', 'verified', 'monitoring']
  const projects = []
  for (let i = 1; i <= count; i++) {
    const readiness = Math.random() * 100
    const alertLevel = readiness > 90 ? 'green' : readiness > 70 ? 'yellow' : 'red'
    const daysSinceActivity = Math.floor(Math.random() * 30)
    const overdue = daysSinceActivity > 14 && readiness < 70
    projects.push({
      id: `proj-${i.toString().padStart(3, '0')}`,
      name: `Project ${i} — ${['Kenya', 'Ghana', 'Guatemala', 'Nepal', 'Ethiopia', 'Uganda'][i % 6]} ${['Clean Cookstoves', 'Biogas', 'LPG Adoption', 'Improved Charcoal'][i % 4]}`,
      methodology: methodologies[i % 4],
      status: statuses[i % 7],
      readiness: Math.round(readiness),
      creditsForecast: Math.round(Math.random() * 50000),
      lastActivityDays: daysSinceActivity,
      alertLevel,
      overdue,
      developer: `Developer ${(i % 20) + 1}`,
    })
  }
  return projects
}

function generateInboxItems(count: number) {
  const types = ['calculation', 'report', 'data_anomaly', 'agent_review', 'vvb_response']
  const items = []
  for (let i = 1; i <= count; i++) {
    const priority = Math.floor(Math.random() * 5) + 1
    const hoursInQueue = Math.random() * 72
    const financialImpact = Math.random() * 50000
    const score = (5 - priority) * hoursInQueue * (financialImpact / 10000)
    items.push({
      id: `item-${i}`,
      priority,
      priorityScore: Math.round(score),
      projectId: `proj-${(i % 200) + 1}`,
      projectName: `Project ${(i % 200) + 1}`,
      itemType: types[i % 5],
      reason: [
        'Confidence below threshold (0.82)',
        'Methodology compliance score 68%',
        'Cross-project anomaly detected',
        'VVB requested clarification on fNRB',
        'Photo GPS outside boundary',
        'Calculation uncertainty >50%',
      ][i % 6],
      confidence: Math.round((0.5 + Math.random() * 0.4) * 100) / 100,
      hoursInQueue: Math.round(hoursInQueue * 10) / 10,
      financialImpact: Math.round(financialImpact),
      suggestedAction: ['Approve with notes', 'Request additional data', 'Escalate to senior reviewer', 'Re-run calculation'][i % 4],
      assignedTo: i % 3 === 0 ? 'John Operator' : null,
      status: i % 4 === 0 ? 'in_review' : 'pending',
    })
  }
  return items.sort((a, b) => b.priorityScore - a.priorityScore)
}

function generateVVBCards() {
  const stages = ['draft', 'submitted', 'under_review', 'clarification_requested', 'approved', 'rejected']
  const cards: Record<string, any[]> = { draft: [], submitted: [], under_review: [], clarification_requested: [], approved: [], rejected: [] }
  for (let i = 1; i <= 45; i++) {
    const stage = stages[i % 6]
    const daysInStage = Math.floor(Math.random() * 20)
    cards[stage].push({
      id: `vvb-${i}`,
      projectId: `proj-${(i % 200) + 1}`,
      projectName: `Project ${(i % 200) + 1}`,
      methodology: ['TPDDTEC_v4', 'VM0050'][i % 2],
      registry: ['Verra', 'Gold Standard'][i % 2],
      daysInStage,
      deadlineWarning: daysInStage > 7 && stage === 'clarification_requested',
      overdue: daysInStage > 14,
      clarificationQuery: stage === 'clarification_requested' ? [
        'Please justify fNRB value of 0.42 for this region.',
        'KPT sample size of 28 is below minimum of 30.',
        'Provide additional evidence for leakage assessment.',
      ][i % 3] : null,
      draftResponse: stage === 'clarification_requested' ? 'Draft response available' : null,
    })
  }
  return cards
}

function generateQualityMetrics() {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
  return {
    accuracyOverTime: months.map((m) => ({ month: m, manual: 92 + Math.random() * 6, automated: 88 + Math.random() * 8 })),
    rejectionByVVB: [
      { name: 'Verra', value: 12 },
      { name: 'Gold Standard', value: 8 },
      { name: 'Kenya National', value: 5 },
    ],
    rejectionByMethodology: [
      { name: 'TPDDTEC v4', value: 15 },
      { name: 'VM0050', value: 10 },
      { name: 'VMR0006', value: 3 },
      { name: 'AMS-II.G', value: 7 },
    ],
    npsTrend: months.map((m) => ({ month: m, nps: Math.round(40 + Math.random() * 30) })),
    supportVolume: months.map((m) => ({ month: m, tickets: Math.round(20 + Math.random() * 40) })),
    calibrationData: Array.from({ length: 50 }, () => ({
      confidence: Math.round((0.6 + Math.random() * 0.35) * 100) / 100,
      accuracy: Math.round((0.5 + Math.random() * 0.45) * 100) / 100,
      agent: ['Ingestion', 'Validation', 'Calculation', 'Reporting'][Math.floor(Math.random() * 4)],
    })),
  }
}

function generateAgentPerformance() {
  const agents = ['IngestionAgent', 'ValidationAgent', 'CalculationAgent', 'ReportingAgent', 'VVBLiaisonAgent', 'QualityControlAgent', 'ClientSuccessAgent']
  return agents.map((name) => ({
    name,
    tasksCompleted: Math.round(500 + Math.random() * 2000),
    avgConfidence: Math.round((0.75 + Math.random() * 0.2) * 100) / 100,
    escalationRate: Math.round(Math.random() * 15 * 10) / 10,
    errorRate: Math.round(Math.random() * 5 * 10) / 10,
    avgExecutionTimeMs: Math.round(200 + Math.random() * 3000),
    humanReviewsRequired: Math.round(Math.random() * 100),
    trend: Array.from({ length: 7 }, () => Math.round((0.7 + Math.random() * 0.25) * 100)),
    improvementSuggestion: name === 'CalculationAgent'
      ? 'Overconfident on fNRB > 0.4 — consider retraining with MoFuSS data'
      : name === 'ValidationAgent'
      ? 'High false-positive rate on outlier detection — adjust threshold'
      : undefined,
  }))
}

const MOCK_PROJECTS = generateProjects(200)
const MOCK_INBOX = generateInboxItems(50)
const MOCK_VVB = generateVVBCards()
const MOCK_QUALITY = generateQualityMetrics()
const MOCK_AGENTS = generateAgentPerformance()

export function useProjectsHealth() {
  return useQuery({
    queryKey: ['projectsHealth'],
    queryFn: async () => {
      // const res = await api.get('/command-center/projects-health')
      // return res.data
      return MOCK_PROJECTS
    },
    staleTime: 60000,
  })
}

export function usePriorityQueue() {
  return useQuery({
    queryKey: ['priorityQueue'],
    queryFn: async () => {
      // const res = await api.get('/command-center/inbox')
      // return res.data
      return MOCK_INBOX
    },
    staleTime: 30000,
  })
}

export function useVVBPipeline() {
  return useQuery({
    queryKey: ['vvbPipeline'],
    queryFn: async () => {
      // const res = await api.get('/command-center/vvb-pipeline')
      // return res.data
      return MOCK_VVB
    },
    staleTime: 60000,
  })
}

export function useQualityMetrics() {
  return useQuery({
    queryKey: ['qualityMetrics'],
    queryFn: async () => {
      // const res = await api.get('/command-center/quality-metrics')
      // return res.data
      return MOCK_QUALITY
    },
    staleTime: 300000,
  })
}

export function useAgentPerformance() {
  return useQuery({
    queryKey: ['agentPerformance'],
    queryFn: async () => {
      // const res = await api.get('/command-center/agent-performance')
      // return res.data
      return MOCK_AGENTS
    },
    staleTime: 300000,
  })
}
