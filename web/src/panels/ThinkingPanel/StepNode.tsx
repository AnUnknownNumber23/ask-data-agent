import React from 'react'
import type { StepData } from '../../App'

export function StepNode({ step, isLatest }: { step: StepData; isLatest?: boolean }) {
  const statusIcon = step.status === 'ok' ? '✅' : step.status === 'warning' ? '⚠️' : '❌'

  return (
    <div className={`step-node status-${step.status}${isLatest ? ' step-running' : ''}`}>
      <div className="step-header">
        <span className="step-icon">{statusIcon}</span>
        <span className="step-name">{step.step}</span>
        <span className="step-duration">{step.duration_ms.toFixed(0)}ms</span>
      </div>
      {step.output && Object.keys(step.output).length > 0 && (
        <div className="step-details">
          {step.output.matched_tables && (
            <div className="detail-row">
              <span className="label">表：</span>
              <span>{step.output.matched_tables.join(', ')}</span>
            </div>
          )}
          {step.output.sql && (
            <div className="detail-row sql-preview">
              <span className="label">SQL：</span>
              <code>{step.output.sql.substring(0, 200)}{step.output.sql.length > 200 ? '...' : ''}</code>
            </div>
          )}
          {step.output.row_count !== undefined && (
            <div className="detail-row">
              <span className="label">行数：</span>
              <span>{step.output.row_count}</span>
            </div>
          )}
          {step.output.retry_count !== undefined && (
            <div className="detail-row">
              <span className="label">重试：</span>
              <span>#{step.output.retry_count}</span>
            </div>
          )}
        </div>
      )}
      {step.error && (
        <div className="step-error">{step.error}</div>
      )}
    </div>
  )
}
