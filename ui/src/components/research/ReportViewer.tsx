import { useCallback } from 'react'
import { Download } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Props = {
  report: string
  query: string
  isStreaming: boolean
  error: string | null
}

function toSafeFileStem(value: string): string {
  return (
    value
      .toLowerCase()
      .trim()
      .replace(/[^\w\s.-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 80) || 'research-report'
  )
}

export function ReportViewer({ report, query, isStreaming, error }: Props) {
  const download = useCallback(() => {
    if (!report.trim()) return
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${toSafeFileStem(query)}-${new Date().toISOString().slice(0, 10)}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [query, report])

  return (
    <Card className="min-h-48">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Report</CardTitle>
          {report && (
            <Button variant="outline" size="sm" onClick={download}>
              <Download size={14} />
              Download
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {error && <p className="text-destructive text-sm">{error}</p>}
        {!error && !report && (
          <p className="text-muted-foreground text-sm">
            {isStreaming ? 'Generating report...' : 'Submit a query to generate a report.'}
          </p>
        )}
        {report && (
          <article className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{report}</ReactMarkdown>
          </article>
        )}
      </CardContent>
    </Card>
  )
}
