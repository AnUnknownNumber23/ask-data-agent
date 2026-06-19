import React from 'react'
import type { TraceData } from '../../App'
import { StepNode } from './StepNode'
import './ThinkingPanel.css'

interface Props {
  trace: TraceData | null
  isProcessing: boolean
}

export function ThinkingPanel({ trace, isProcessing }: Props) {
  if (!trace) {
    return (
      <div className="thinking-panel">
        <h3>思考过程</h3>
        <p className="placeholder">提问后这里会实时展示 Agent 的推理步骤。</p>
      </div>
    )
  }

  const totalDuration = trace.steps.reduce((sum, s) => sum + s.duration_ms, 0)

  return (
    <div className="thinking-panel">
      <h3>思考过程 {isProcessing && <span className="spinner" />}</h3>
      <div className="trace-meta">
        <span>问题：<em>{trace.user_query}</em></span>
        <span className="trace-id">ID: {trace.trace_id}</span>
      </div>

      <div className="steps-list">
        {trace.steps.map((step, i) => {
          const isLatest = i === trace.steps.length - 1
          return <StepNode key={i} step={step} isLatest={isLatest && isProcessing} />
        })}
      </div>

      {trace.evaluator_results && trace.evaluator_results.length > 0 && (
        <div className="evaluator-section">
          <h4>评估结果</h4>
          {trace.evaluator_results.map((r, i) => (
            <div key={i} className={`eval-badge verdict-${r.verdict}`}>
              Gate {r.gate}: {r.verdict.toUpperCase()} (score: {r.score?.toFixed(2) || 'N/A'})
            </div>
          ))}
        </div>
      )}

      <div className="trace-footer">
        <span>⏱ {(totalDuration / 1000).toFixed(2)}s</span>
        {isProcessing && <span className="pulse-dot">● 运行中</span>}
        {trace.total_tokens && (
          <span>📊 {trace.total_tokens.input || 0}+{trace.total_tokens.output || 0} tokens</span>
        )}
      </div>
    </div>
  )
}
