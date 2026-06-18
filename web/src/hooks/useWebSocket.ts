import { useRef, useEffect, useState, useCallback } from 'react'

interface UseWebSocketOptions {
  onMessage: (data: any) => void
  onError?: (error: string) => void
}

export function useWebSocket(url: string, options: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectRef = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
    }

    ws.onclose = () => {
      setIsConnected(false)
      reconnectRef.current = setTimeout(connect, 3000)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        options.onMessage(data)
      } catch { /* ignore */ }
    }

    ws.onerror = () => {
      options.onError?.('WebSocket connection error')
    }
  }, [url])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
    }
  }, [connect])

  const sendQuery = useCallback((query: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ query }))
    }
  }, [])

  return { sendQuery, isConnected }
}
