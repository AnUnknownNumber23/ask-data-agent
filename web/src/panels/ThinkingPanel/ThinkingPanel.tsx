import React from 'react'
import type { TraceData } from '../../App'
import { StepNode } from './StepNode'
import './ThinkingPanel.css'

interface Props {
  trace: TraceData | null
}

export function ThinkingPanel({ trace }: Props) {
  if (!trace) {
    return (
      <div className="thinking-panel">
        <h3>Thinking Process</h3>
        <p className="placeholder">Ask a question to see the agent's reasoning steps in real-time.</p>
      </div>
    )
  }

  const totalDuration = trace.steps.reduce((sum, s) => sum + s.duration_ms, 0)

  return (
    <div className="thinking-panel">
      <h3>Thinking Process</h3>
      <div className="trace-meta">
        <span>Query: <em>{trace.user_query}</em></span>
        <span className="trace-id">ID: {trace.trace_id}</span>
      </div>

      <div className="steps-list">
        {trace.steps.map((step, i) => (
          <StepNode key={i} step={step} />
        ))}
      </div>

      {trace.evaluator_results && trace.evaluator_results.length > 0 && (
        <div className="evaluator-section">
          <h4>Evaluator Results</h4>
          {trace.evaluator_results.map((r, i) => (
            <div key={i} className={`eval-badge verdict-${r.verdict}`}>
              Gate {r.gate}: {r.verdict.toUpperCase()} (score: {r.score?.toFixed(2) || 'N/A'})
            </div>
          ))}
        </div>
      )}

      <div className="trace-footer">
        <span>⏱ {(totalDuration / 1000).toFixed(2)}s</span>
        {trace.total_tokens && (
          <span>📊 {trace.total_tokens.input || 0}+{trace.total_tokens.output || 0} tokens</span>
        )}
      </div>
    </div>
  )
}
