import { useEffect, useRef, useCallback } from 'react'
import { useNotificationStore } from '../stores/notificationStore'
import { useAuthStore } from '../stores/authStore'

function getBaseWSUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL
  // In dev, connect through the Vite proxy (same origin) to avoid CORS issues
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/notifications`
}

function getWSUrl(): string {
  const token = useAuthStore.getState().accessToken
  const base = getBaseWSUrl()
  if (!token) return base
  const separator = base.includes('?') ? '&' : '?'
  return `${base}${separator}token=${encodeURIComponent(token)}`
}

export function useCommandWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number | null>(null)
  const addNotification = useNotificationStore((s) => s.addNotification)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return

    try {
      const WS_URL = getWSUrl()
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        // WebSocket connected
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'human_review_queued') {
            addNotification({
              id: `hr-${data.queue_item_id}`,
              type: 'human_review_required',
              title: 'Human Review Required',
              message: `${data.agent_type} on project ${data.project_id} needs review (priority: ${data.priority})`,
              projectId: data.project_id,
              severity: data.priority >= 4 ? 'critical' : 'warning',
              read: false,
              timestamp: new Date().toISOString(),
              actionUrl: '/command-center/inbox',
            })
          } else if (data.type === 'vvb_clarification_received') {
            addNotification({
              id: `vvb-${Date.now()}`,
              type: 'vvb_clarification_received',
              title: 'VVB Clarification Received',
              message: data.message || 'New clarification request from VVB',
              projectId: data.project_id,
              severity: 'warning',
              read: false,
              timestamp: new Date().toISOString(),
              actionUrl: '/command-center/vvb',
            })
          } else if (data.type === 'calculation_anomaly_detected') {
            addNotification({
              id: `anom-${Date.now()}`,
              type: 'calculation_anomaly_detected',
              title: 'Calculation Anomaly',
              message: data.detail || 'Cross-project anomaly detected',
              projectId: data.project_id,
              severity: 'critical',
              read: false,
              timestamp: new Date().toISOString(),
              actionUrl: '/command-center/inbox',
            })
          } else if (data.type === 'agent_escalation') {
            addNotification({
              id: `esc-${Date.now()}`,
              type: 'agent_escalation',
              title: 'Agent Escalation',
              message: `${data.agent_type} confidence too low — requires immediate attention`,
              projectId: data.project_id,
              severity: 'critical',
              read: false,
              timestamp: new Date().toISOString(),
              actionUrl: '/command-center/inbox',
            })
          } else if (data.type === 'deadline_warning') {
            addNotification({
              id: `dl-${Date.now()}`,
              type: 'deadline_warning',
              title: 'Deadline Warning',
              message: data.message || 'Upcoming deadline',
              projectId: data.project_id,
              severity: 'warning',
              read: false,
              timestamp: new Date().toISOString(),
              actionUrl: '/command-center/vvb',
            })
          }
        } catch {
          // ignore invalid JSON
        }
      }

      ws.current.onclose = () => {
        reconnectTimer.current = window.setTimeout(connect, 5000)
      }

      ws.current.onerror = () => {
        // WebSocket error handled by onclose reconnection
      }
    } catch {
      reconnectTimer.current = window.setTimeout(connect, 5000)
    }
  }, [addNotification])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  const send = useCallback((msg: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg))
    }
  }, [])

  return { send, connected: ws.current?.readyState === WebSocket.OPEN }
}
