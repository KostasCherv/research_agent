import type { ReactNode } from 'react'

type LayoutProps = {
  title: string
  subtitle: string
  status: {
    label: string
    icon: ReactNode
  }
  children: ReactNode
}

export function Layout({ title, subtitle, status, children }: LayoutProps) {
  return (
    <div className="page-shell">
      <header className="glass-panel header-panel">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div className="status-badge" aria-live="polite">
          {status.icon}
          <span>{status.label}</span>
        </div>
      </header>
      <main className="content-grid">{children}</main>
    </div>
  )
}
