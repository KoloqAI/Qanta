const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`

interface WsSubscription {
  unsubscribe: () => void
}

export function subscribeWs(
  path: string,
  onMessage: (data: unknown) => void,
  onStatusChange?: (status: 'connected' | 'disconnected' | 'reconnecting') => void,
): WsSubscription {
  let ws: WebSocket | null = null
  let active = true
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined

  function connect() {
    if (!active) return
    onStatusChange?.('reconnecting')
    ws = new WebSocket(`${WS_BASE}${path}`)

    ws.onopen = () => onStatusChange?.('connected')

    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data))
      } catch {
        onMessage(e.data)
      }
    }

    ws.onclose = () => {
      if (!active) return
      onStatusChange?.('disconnected')
      reconnectTimer = setTimeout(connect, 2000)
    }

    ws.onerror = () => ws?.close()
  }

  connect()

  return {
    unsubscribe() {
      active = false
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close()
    },
  }
}
