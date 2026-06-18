import React from 'react'
import type { Message } from '../../App'
import ReactECharts from 'echarts-for-react'
import './ChatPanel.css'

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

  return (
    <div className={`message-bubble ${message.role}`}>
      <div className="message-role">{message.role === 'user' ? 'You' : 'Agent'}</div>
      <div className="message-content">{message.content}</div>
      {chartOption && (
        <div className="message-chart">
          <ReactECharts option={chartOption} style={{ height: 300 }} />
        </div>
      )}
    </div>
  )
}
