import { useCallback } from 'react'
import ReactMarkdown from 'react-markdown'

type ReportViewerProps = {
  report: string
  query: string
  isStreaming: boolean
  error: string | null
}

function toSafeFileStem(value: string): string {
  const normalized = value
    .toLowerCase()
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')

  return normalized.slice(0, 80) || 'research-report'
}

export function ReportViewer({ report, query, isStreaming, error }: ReportViewerProps) {
  const handleDownloadMarkdown = useCallback(() => {
    if (!report.trim()) {
      return
    }

    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    const dateStamp = new Date().toISOString().slice(0, 10)
    const queryStem = toSafeFileStem(query)
    anchor.href = url
    anchor.download = `${queryStem}-${dateStamp}.md`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  }, [query, report])

  return (
    <section className="glass-panel card-spacing report-panel">
      <div className="report-header">
        <h2>Report</h2>
        {report && (
          <button
            type="button"
            className="submit-button report-download-button"
            onClick={handleDownloadMarkdown}
          >
            Download Markdown
          </button>
        )}
      </div>
      {error && <p className="error-banner">{error}</p>}
      {!error && !report && (
        <p className="empty-state">
          {isStreaming
            ? 'Waiting for report content...'
            : 'Submit a query to generate a markdown report.'}
        </p>
      )}
      {report && (
        <article className="markdown-content">
          <ReactMarkdown>{report}</ReactMarkdown>
        </article>
      )}
    </section>
  )
}
