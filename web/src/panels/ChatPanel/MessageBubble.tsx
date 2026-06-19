import React from 'react'
import type { Message } from '../../App'
import ReactECharts from 'echarts-for-react'
import './ChatPanel.css'

function renderMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\[📥 Markdown\]/g, '<a href="#" data-download="md" class="download-link">📥 Markdown</a>')
    .replace(/\[📄 PDF\]/g, '<a href="#" data-download="pdf" class="download-link pdf-link">📄 PDF</a>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>')
}

async function handleDownload(e: React.MouseEvent, message: Message) {
  const target = e.target as HTMLElement
  const link = target.closest('[data-download]') as HTMLElement | null
  if (!link) return
  e.preventDefault()

  const format = link.dataset.download
  if (format === 'md' && message._reportContent) {
    // Markdown: download directly from stored content
    const blob = new Blob([message._reportContent], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${message._reportTitle || 'report'}.md`
    a.click(); URL.revokeObjectURL(url)
  } else if (format === 'pdf' && message._reportTitle) {
    // PDF: fetch from API (regenerates report, slow)
    link.textContent = ' 生成中...'
    try {
      const q = message._reportTitle.replace(/^Report:\s*/, '')
      const resp = await fetch(`http://${window.location.hostname}:8014/api/reports/export/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, template: 'weekly' }),
      })
      if (resp.ok) {
        const blob = await resp.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = `${q}.pdf`
        a.click(); URL.revokeObjectURL(url)
      }
    } catch (err: any) {
      console.error('PDF export failed:', err)
    } finally {
      link.textContent = '📄 PDF'
    }
  }
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
    <div className={`message-bubble ${message.role}${isReport ? ' report' : ''}`}
      onClick={(e) => handleDownload(e, message)}>
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
