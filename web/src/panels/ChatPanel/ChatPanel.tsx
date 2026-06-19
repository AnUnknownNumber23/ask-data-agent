import React, { useState, useRef, useEffect } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import { MessageBubble } from './MessageBubble'
import type { TraceData, Message } from '../../App'
import './ChatPanel.css'

interface Props {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setTrace: React.Dispatch<React.SetStateAction<TraceData | null>>
  isProcessing: boolean
  setIsProcessing: React.Dispatch<React.SetStateAction<boolean>>
  streaming: string
  setStreaming: React.Dispatch<React.SetStateAction<string>>
}

export function ChatPanel({ messages, setMessages, setTrace, isProcessing, setIsProcessing, streaming, setStreaming }: Props) {
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(
    () => localStorage.getItem('ask-data-session') || ''
  )
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // Connect directly to backend (port from VITE_API_PORT env)
  const apiPort = import.meta.env.VITE_API_PORT || '8013'
  const wsUrl = `${protocol}//${window.location.hostname}:${apiPort}/api/ws/chat`
  const { sendQuery, isConnected } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      console.log('[ChatPanel] onMessage:', Object.keys(data), data.type || '(trace)')
      // Session handshake — save session ID for persistence
      if (data.type === 'session') {
        if (data.session_id && !sessionId) {
          setSessionId(data.session_id)
          localStorage.setItem('ask-data-session', data.session_id)
        }
        return
      }
      // Streaming token — append to current answer in real-time
      if (data.type === 'stream') {
        setStreaming(prev => prev + (data.token || ''))
        return
      }
      // Incremental trace update (has trace_id but no type field)
      if (data.trace_id && !data.type) {
        setTrace({
          trace_id: data.trace_id,
          session_id: data.session_id,
          user_query: data.user_query,
          steps: data.steps || [],
          evaluator_results: data.evaluator_results || [],
          total_tokens: data.total_tokens,
        })
        return
      }
      // Final result
      if (data.type === 'done') {
        setIsProcessing(false)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.answer || streaming || 'Analysis complete.',
          chart: data.chart,
        }])
        setStreaming('')
        if (data.trace) setTrace(data.trace)
        return
      }
      // Error
      if (data.type === 'error') {
        setIsProcessing(false)
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Error: ${data.message || 'Unknown error'}`,
        }])
      }
    },
    onError: (err) => {
      setIsProcessing(false)
      setMessages(prev => [...prev, { role: 'system', content: `Error: ${err}` }])
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || isProcessing) return
    setMessages(prev => [...prev, { role: 'user', content: input }])
    setTrace(null)
    setStreaming('')
    setIsProcessing(true)
    sendQuery(input, sessionId)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2>ask-data-agent</h2>
        <span className={`connection-status ${isConnected ? 'connected' : ''}`}>
          {isConnected ? '● Connected' : '○ Connecting...'}
        </span>
      </div>
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h3>Ask your data questions</h3>
            <p>Example: "Show me monthly GMV by state"</p>
            <p>Example: "Which product category has the highest review score?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {streaming && (
          <div className="message-bubble assistant streaming">
            <div className="message-role">ASSISTANT</div>
            <div className="message-content">{streaming}</div>
            <span className="cursor-blink">|</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="input-container">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask your data question..."
          rows={3}
        />
        {isProcessing && (
          <div className="processing-indicator">
            <span className="spinner" />
            Agent is thinking...
          </div>
        )}
        <button onClick={handleSend} disabled={!isConnected || isProcessing}>
          {isProcessing ? 'Thinking...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
