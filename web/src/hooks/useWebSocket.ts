import { useRef, useEffect, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  onMessage: (data: any) => void
  onError?: (error: string) => void
}

export function useWebSocket(url: string, options: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const connIdRef = useRef(0)  // increment on each (re)connect to avoid stale refs
  const hasEverConnected = useRef(false)  // suppress error on initial connection

  // Store callbacks in refs so they're always current
  const onMessageRef = useRef(options.onMessage)
  onMessageRef.current = options.onMessage
  const onErrorRef = useRef(options.onError)
  onErrorRef.current = options.onError

  // One-time connect on mount, reconnect on url change
  useEffect(() => {
    let active = true
    connIdRef.current += 1
    const thisConn = connIdRef.current

    function doConnect() {
      if (!active) return

      // Clean old socket
      if (wsRef.current) {
        wsRef.current.onopen = null
        wsRef.current.onclose = null
        wsRef.current.onmessage = null
        wsRef.current.onerror = null
        try { wsRef.current.close() } catch (_) { /* ignore */ }
        wsRef.current = null
      }

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!active || connIdRef.current !== thisConn) return
        hasEverConnected.current = true
        setIsConnected(true)
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = undefined
        }
      }

      ws.onclose = () => {
        if (!active || connIdRef.current !== thisConn) return
        setIsConnected(false)
        wsRef.current = null
        // Auto-reconnect after 3s
        if (active) {
          reconnectTimer.current = setTimeout(doConnect, 3000)
        }
      }

      ws.onmessage = (event) => {
        if (!active || connIdRef.current !== thisConn) return
        try {
          onMessageRef.current(JSON.parse(event.data))
        } catch { /* ignore */ }
      }

      ws.onerror = () => {
        if (!active || connIdRef.current !== thisConn) return
        // Suppress error on initial connection attempt — backend may not be ready yet
        if (!hasEverConnected.current) return
        onErrorRef.current?.('WebSocket connection error')
      }
    }

    doConnect()

    return () => {
      active = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      connIdRef.current += 1  // invalidate any pending callbacks
      if (wsRef.current) {
        wsRef.current.onopen = null
        wsRef.current.onclose = null
        wsRef.current.onmessage = null
        wsRef.current.onerror = null
        try { wsRef.current.close() } catch (_) { /* ignore */ }
        wsRef.current = null
      }
      setIsConnected(false)
    }
  }, [url])

  const sendQuery = useCallback((query: string, sessionId?: string) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const payload: Record<string, string> = { query }
    if (sessionId) payload.session_id = sessionId
    ws.send(JSON.stringify(payload))
  }, [])

  return { sendQuery, isConnected }
}
