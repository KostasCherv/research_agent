import { useCallback, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { StructuredReportV2, Claim, SourceAssessment } from '../types'

const LOW_CONFIDENCE_THRESHOLD = 0.5

type ReportViewerProps = {
  report: string
  query: string
  isStreaming: boolean
  error: string | null
  structuredReport?: StructuredReportV2
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

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100)
  const isLow = confidence < LOW_CONFIDENCE_THRESHOLD
  return (
    <span
      className={`confidence-badge ${isLow ? 'confidence-badge--low' : 'confidence-badge--ok'}`}
      title={`Confidence: ${pct}%`}
    >
      {pct}%
    </span>
  )
}

function ClaimCard({ claim }: { claim: Claim }) {
  const isLow = claim.confidence < LOW_CONFIDENCE_THRESHOLD
  return (
    <div className={`claim-card ${isLow ? 'claim-card--low-confidence' : ''}`}>
      <div className="claim-header">
        <span className="claim-id">{claim.id}</span>
        <ConfidenceBadge confidence={claim.confidence} />
        {isLow && <span className="claim-warning">⚠ Low confidence</span>}
      </div>
      <p className="claim-text">{claim.text}</p>
      {claim.evidence_quote && (
        <blockquote className="claim-quote">{claim.evidence_quote}</blockquote>
      )}
      {claim.evidence_source_urls.length > 0 && (
        <div className="claim-citations">
          {claim.evidence_source_urls.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="citation-chip"
            >
              source
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

function SourceRow({ assessment }: { assessment: SourceAssessment }) {
  const pct = Math.round(assessment.reliability_score * 100)
  const flags = assessment.bias_flags.length > 0 ? assessment.bias_flags.join(', ') : 'none'
  const age = assessment.freshness_days != null ? `${assessment.freshness_days}d` : 'unknown'
  return (
    <tr className="source-row">
      <td>
        <a href={assessment.url} target="_blank" rel="noopener noreferrer" className="source-url">
          {assessment.url}
        </a>
      </td>
      <td>
        <span className={pct >= 70 ? 'reliability--high' : pct >= 40 ? 'reliability--mid' : 'reliability--low'}>
          {pct}%
        </span>
      </td>
      <td>{flags}</td>
      <td>{age}</td>
    </tr>
  )
}

function StructuredView({ report }: { report: StructuredReportV2 }) {
  const lowCount = report.claims.filter((c) => c.confidence < LOW_CONFIDENCE_THRESHOLD).length

  return (
    <div className="structured-view">
      <h2 className="structured-title">{report.title}</h2>

      <section className="structured-section">
        <h3>Executive Summary</h3>
        <p>{report.executive_summary}</p>
      </section>

      {lowCount > 0 && (
        <div className="confidence-summary-banner">
          ⚠ {lowCount} claim{lowCount > 1 ? 's' : ''} below {LOW_CONFIDENCE_THRESHOLD * 100}% confidence — verify before citing.
        </div>
      )}

      <section className="structured-section">
        <h3>Claims ({report.claims.length})</h3>
        <div className="claims-list">
          {report.claims.map((claim) => (
            <ClaimCard key={claim.id} claim={claim} />
          ))}
        </div>
      </section>

      <section className="structured-section">
        <h3>Conclusion</h3>
        <p>{report.conclusion}</p>
      </section>

      {report.source_assessments.length > 0 && (
        <section className="structured-section">
          <h3>Source Assessments</h3>
          <table className="source-table">
            <thead>
              <tr>
                <th>URL</th>
                <th>Reliability</th>
                <th>Flags</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {report.source_assessments.map((sa) => (
                <SourceRow key={sa.url} assessment={sa} />
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

export function ReportViewer({ report, query, isStreaming, error, structuredReport }: ReportViewerProps) {
  const [viewMode, setViewMode] = useState<'markdown' | 'structured'>('markdown')

  const handleDownloadMarkdown = useCallback(() => {
    if (!report.trim()) return

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

  const canShowStructured = Boolean(structuredReport && structuredReport.claims?.length > 0)

  return (
    <section className="glass-panel card-spacing report-panel">
      <div className="report-header">
        <h2>Report</h2>
        <div className="report-header-actions">
          {canShowStructured && (
            <div className="view-toggle">
              <button
                type="button"
                className={`toggle-btn ${viewMode === 'markdown' ? 'toggle-btn--active' : ''}`}
                onClick={() => setViewMode('markdown')}
              >
                Markdown
              </button>
              <button
                type="button"
                className={`toggle-btn ${viewMode === 'structured' ? 'toggle-btn--active' : ''}`}
                onClick={() => setViewMode('structured')}
              >
                Structured
              </button>
            </div>
          )}
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
      </div>

      {error && <p className="error-banner">{error}</p>}

      {!error && !report && (
        <p className="empty-state">
          {isStreaming
            ? 'Waiting for report content...'
            : 'Submit a query to generate a markdown report.'}
        </p>
      )}

      {report && viewMode === 'markdown' && (
        <article className="markdown-content">
          <ReactMarkdown>{report}</ReactMarkdown>
        </article>
      )}

      {canShowStructured && viewMode === 'structured' && structuredReport && (
        <StructuredView report={structuredReport} />
      )}
    </section>
  )
}
