import { useState } from 'react'
import { ChatPanel } from './panels/ChatPanel/ChatPanel'
import { ThinkingPanel } from './panels/ThinkingPanel/ThinkingPanel'
import './App.css'

export interface TraceData {
  trace_id: string
  session_id: string
  user_query: string
  steps: StepData[]
  evaluator_results: EvalData[]
  total_tokens?: Record<string, number>
}

export interface StepData {
  step: string
  status: 'ok' | 'warning' | 'error'
  duration_ms: number
  output: Record<string, any>
  error?: string
}

export interface EvalData {
  gate: number
  score: number
  verdict: string
}

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  chart?: any
  _reportTitle?: string
  _reportContent?: string
}

function App() {
  const [trace, setTrace] = useState<TraceData | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [streaming, setStreaming] = useState('')

  return (
    <div className="app-layout">
      <div className="chat-panel-container">
        <ChatPanel
          messages={messages} setMessages={setMessages}
          setTrace={setTrace}
          isProcessing={isProcessing} setIsProcessing={setIsProcessing}
          streaming={streaming} setStreaming={setStreaming}
        />
      </div>
      <div className="thinking-panel-container">
        <ThinkingPanel trace={trace} isProcessing={isProcessing} />
      </div>
    </div>
  )
}

export default App
