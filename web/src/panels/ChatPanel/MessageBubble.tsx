import React from 'react'
import type { Message } from '../../App'
import ReactECharts from 'echarts-for-react'
import './ChatPanel.css'

function renderMarkdown(text: string): string {
  // Simple markdown → HTML for headers, bold, line breaks
  return text
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}

export function MessageBubble({ message }: { message: Message }) {
  const chartOption = message.chart ? {
    xAxis: { type: 'category', data: message.chart.x || [] },
    yAxis: { type: 'value' },
    series: (message.chart.series || []).map((s: any) => ({
      type: message.chart?.chart_type || 'bar',
      data: s.data || [],
      name: s.name || '',
    })),
    tooltip: { trigger: 'axis' },
  } : null

  const isReport = message.content.startsWith('# ')
  const roleLabels: Record<string, string> = { user: '你', assistant: '助手', system: '系统' }

  return (
    <div className={`message-bubble ${message.role}${isReport ? ' report' : ''}`}>
      <div className="message-role">{roleLabels[message.role] || message.role}</div>
      <div className="message-content"
        dangerouslySetInnerHTML={message.role === 'user'
          ? undefined
          : { __html: renderMarkdown(message.content) }}>
        {message.role === 'user' ? message.content : undefined}
      </div>
      {chartOption && (
        <div className="message-chart">
          <ReactECharts option={chartOption} style={{ height: 300 }} />
        </div>
      )}
    </div>
  )
}
