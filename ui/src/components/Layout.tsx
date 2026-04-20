import type { ReactNode } from 'react'

type LayoutProps = {
  title: string
  subtitle: string
  status: {
    label: string
    icon: ReactNode
  }
  actions?: ReactNode
  sidebar?: ReactNode
  children: ReactNode
}

export function Layout({ title, subtitle, status, actions, sidebar, children }: LayoutProps) {
  return (
    <div className="page-shell">
      <header className="glass-panel header-panel">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div className="header-controls">
          {actions}
          <div className="status-badge" aria-live="polite">
            {status.icon}
            <span>{status.label}</span>
          </div>
        </div>
      </header>
      <div className={`layout-body ${sidebar ? 'layout-body--with-sidebar' : 'layout-body--full'}`}>
        {sidebar ? <aside className="glass-panel sidebar-panel">{sidebar}</aside> : null}
        <main className="content-grid">{children}</main>
      </div>
    </div>
  )
}
