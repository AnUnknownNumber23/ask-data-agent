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
  const apiPort = import.meta.env.VITE_API_PORT || '8014'
  const wsUrl = `${protocol}//${window.location.hostname}:${apiPort}/api/ws/chat`
  const { sendQuery, isConnected } = useWebSocket(wsUrl, {
    onMessage: (data) => {
      if (data.type === 'session') {
        if (data.session_id && !sessionId) {
          setSessionId(data.session_id)
          localStorage.setItem('ask-data-session', data.session_id)
        }
        return
      }
      if (data.type === 'stream') {
        setStreaming(prev => prev + (data.token || ''))
        return
      }
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
      if (data.type === 'done') {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        setIsProcessing(false)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.answer || streaming || '分析完成。',
          chart: data.chart,
        }])
        setStreaming('')
        if (data.trace) setTrace(data.trace)
        return
      }
      if (data.type === 'error') {
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        setIsProcessing(false)
        setStreaming('')
        setMessages(prev => [...prev, {
          role: 'system',
          content: `错误：${data.message || '未知错误'}`,
        }])
      }
    },
    onError: (err) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      setIsProcessing(false)
      setStreaming('')
      // Show in status, not as chat bubble
      console.error('WebSocket error:', err)
    },
  })

  useEffect(() => {
    try {
      const saved = localStorage.getItem('ask-data-messages')
      if (saved && messages.length === 0) {
        const parsed = JSON.parse(saved)
        if (parsed.length) setMessages(parsed)
      }
    } catch { /* ignore */ }
  }, [])

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
    const query = input.trim().replace(/^report:\s*/i, '')
    setMessages(prev => [...prev, { role: 'user', content: `生成报告：${query}` }])
    setInput('')
    setIsProcessing(true)
    setStreaming('正在生成报告（约 1-2 分钟）...')
    if (timeoutRef.current) clearTimeout(timeoutRef.current)

    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 180000)
      const resp = await fetch(`http://${window.location.hostname}:${apiPort}/api/reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, template: 'weekly' }),
        signal: controller.signal,
      })
      clearTimeout(timeout)
      const data = await resp.json()
      if (resp.ok && data.report) {
        const rpt = data.report
        if (rpt.sections && rpt.sections.length > 0) {
          const sections = rpt.sections.map((s: any) =>
            `## ${s.title}\n\n${s.insight || '暂无数据。'}\n`
          ).join('\n')
          const content = `# ${rpt.title}\n\n${sections}\n\n[📥 Markdown] [📄 PDF]`
          setMessages(prev => [...prev, {
            role: 'assistant',
            content,
            chart: undefined,
            _reportTitle: rpt.title,
            _reportContent: `# ${rpt.title}\n\n${sections}`,
          }])
        } else {
          setMessages(prev => [...prev, {
            role: 'system',
            content: `报告生成失败：返回了空的章节数据`,
          }])
        }
      } else {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `报告失败：${data.detail || '未知错误'}`,
        }])
      }
    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: 'system',
        content: e.name === 'AbortError' ? '报告生成超时（3 分钟），请简化查询后重试。' : `报告错误：${e.message}`,
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
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      setIsProcessing(false)
      setStreaming('')
      setMessages(prev => [...prev, {
        role: 'system',
        content: '请求超时（60 秒），请尝试更简单的查询或重试。',
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
            {isConnected ? '● 已连接' : '○ 等待后端...'}
          </span>
          {messages.length > 0 && (
            <button className="clear-btn" onClick={handleClear} title="清空对话">
              清空
            </button>
          )}
        </div>
      </div>
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h3>向你的数据提问</h3>
            <p>例如："每个月 GMV 趋势如何？"</p>
            <p>例如："哪个品类的评分最高？"</p>
            <p>点击 <b>发送</b> 提问，点击 <b>报告</b> 生成分析报告</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {streaming && (
          <div className="message-bubble assistant streaming">
            <div className="message-role">助手</div>
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
          placeholder="输入问题后点「发送」，或点「报告」生成分析报告..."
          rows={3}
        />
        {isProcessing && (
          <div className="processing-indicator">
            <span className="spinner" />
            {streaming || '思考中...'}
          </div>
        )}
        <button onClick={handleSend} disabled={!isConnected || isProcessing}>
          {isProcessing ? '等待中' : '发送'}
        </button>
        <button onClick={handleGenerateReport} disabled={!isConnected || isProcessing} className="report-btn">
          报告
        </button>
      </div>
    </div>
  )
}
