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
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

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
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
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
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        setIsProcessing(false)
        setStreaming('')
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Error: ${data.message || 'Unknown error'}`,
        }])
      }
    },
    onError: (err) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      setIsProcessing(false)
      setStreaming('')
      setMessages(prev => [...prev, { role: 'system', content: `Connection error: ${err}` }])
    },
  })

  // Restore messages from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('ask-data-messages')
      if (saved && messages.length === 0) {
        const parsed = JSON.parse(saved)
        if (parsed.length) setMessages(parsed)
      }
    } catch { /* ignore */ }
  }, [])

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('ask-data-messages', JSON.stringify(messages.slice(-20)))
    }
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleClear = () => {
    setMessages([])
    setTrace(null)
    setStreaming('')
    localStorage.removeItem('ask-data-messages')
  }

  const handleGenerateReport = async () => {
    if (!input.trim() || isProcessing) return
    const query = input.trim()
    setMessages(prev => [...prev, { role: 'user', content: `Report: ${query}` }])
    setInput('')
    setIsProcessing(true)
    setStreaming('Generating report (1-2 min)...')
    if (timeoutRef.current) clearTimeout(timeoutRef.current)

    try {
      const apiPort = import.meta.env.VITE_API_PORT || '8014'
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 180000)  // 3 min timeout
      const resp = await fetch(`http://${window.location.hostname}:${apiPort}/api/reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, template: 'topic' }),
        signal: controller.signal,
      })
      clearTimeout(timeout)
      const data = await resp.json()
      if (resp.ok && data.report) {
        const rpt = data.report
        if (rpt.sections && rpt.sections.length > 0) {
          const sections = rpt.sections.map((s: any) =>
            `## ${s.title}\n\n${s.insight || 'No data available.'}`
          ).join('\n\n')
          const content = `# ${rpt.title}\n\n${sections}\n\n---\n*Report generated. [Download Markdown](http://${window.location.hostname}:${apiPort}/api/reports/export/markdown)*`
          setMessages(prev => [...prev, { role: 'assistant', content }])
        } else {
          setMessages(prev => [...prev, {
            role: 'system',
            content: `Report generated but returned empty sections. Raw: ${JSON.stringify(rpt).substring(0, 500)}`
          }])
        }
      } else {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Report failed: ${data.detail || 'Unknown error'}`,
        }])
      }
    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: `Report error: ${e.message}`,
      }])
    } finally {
      setIsProcessing(false)
      setStreaming('')
    }
  }

  const handleSend = () => {
    if (!input.trim() || isProcessing) return
    setMessages(prev => [...prev, { role: 'user', content: input }])
    setTrace(null)
    setStreaming('')
    setIsProcessing(true)
    sendQuery(input, sessionId)
    setInput('')
    // Timeout — stop spinning after 60s with a friendly message
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setIsProcessing(false)
      setStreaming('')
      setMessages(prev => [...prev, {
        role: 'system',
        content: 'Request timed out after 60s. The agent may be overloaded — please try a simpler query or try again.',
      }])
    }, 60000)
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
        <div className="chat-header-right">
          <span className={`connection-status ${isConnected ? 'connected' : ''}`}>
            {isConnected ? '● Connected' : '○ Connecting...'}
          </span>
          {messages.length > 0 && (
            <button className="clear-btn" onClick={handleClear} title="Clear conversation">
              Clear
            </button>
          )}
        </div>
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
          placeholder="Ask a question (Send) or generate a report (Report)..."
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
        <button onClick={handleGenerateReport} disabled={!isConnected || isProcessing} className="report-btn">
          Report
        </button>
      </div>
    </div>
  )
}
