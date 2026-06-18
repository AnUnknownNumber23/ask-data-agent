import React, { useState, useRef, useEffect } from 'react'
import { useWebSocket } from '../../hooks/useWebSocket'
import { MessageBubble } from './MessageBubble'
import type { TraceData, Message } from '../../App'
import './ChatPanel.css'

interface Props {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setTrace: React.Dispatch<React.SetStateAction<TraceData | null>>
}

export function ChatPanel({ messages, setMessages, setTrace }: Props) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { sendQuery, isConnected } = useWebSocket('ws://localhost:8000/api/ws/chat', {
    onMessage: (data) => {
      if (data.trace) {
        setTrace(data.trace)
      }
      if (data.type === 'done') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.answer || 'Analysis complete.',
          chart: data.chart,
        }])
        if (data.trace) setTrace(data.trace)
      }
    },
    onError: (err) => {
      setMessages(prev => [...prev, { role: 'system', content: `Error: ${err}` }])
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim()) return
    setMessages(prev => [...prev, { role: 'user', content: input }])
    sendQuery(input)
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
        <button onClick={handleSend} disabled={!isConnected}>
          Send
        </button>
      </div>
    </div>
  )
}
