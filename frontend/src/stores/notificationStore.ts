import { create } from 'zustand'

export interface Notification {
  id: string
  type: 'human_review_required' | 'vvb_clarification_received' | 'calculation_anomaly_detected' | 'client_churn_risk' | 'deadline_warning' | 'agent_escalation'
  title: string
  message: string
  projectId?: string
  projectName?: string
  severity: 'critical' | 'warning' | 'info'
  read: boolean
  timestamp: string
  actionUrl?: string
}

interface NotificationState {
  notifications: Notification[]
  unreadCount: number
  addNotification: (n: Notification) => void
  markRead: (id: string) => void
  markAllRead: () => void
  dismiss: (id: string) => void
  clearAll: () => void
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  addNotification: (n) => {
    const exists = get().notifications.find((x) => x.id === n.id)
    if (exists) return
    set((state) => ({
      notifications: [n, ...state.notifications].slice(0, 200),
      unreadCount: state.unreadCount + (n.read ? 0 : 1),
    }))
  },
  markRead: (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    }))
  },
  markAllRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },
  dismiss: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
      unreadCount: Math.max(0, state.unreadCount - (state.notifications.find((n) => n.id === id)?.read ? 0 : 1)),
    }))
  },
  clearAll: () => set({ notifications: [], unreadCount: 0 }),
}))
