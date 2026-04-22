import { useCallback, useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import { checkHealth } from './api/client'
import { Navbar } from './components/layout/Navbar'
import { supabase } from './lib/supabase'
import type { HealthResponse } from './types'
import { AgentsPage } from './pages/AgentsPage'
import { ResearchPage } from './pages/ResearchPage'
import { ResourcesPage } from './pages/ResourcesPage'

type HealthState = 'loading' | 'online' | 'offline'

function App() {
  const [health, setHealth] = useState<HealthState>('loading')
  const [authSession, setAuthSession] = useState<Session | null>(null)

  useEffect(() => {
    void checkHealth()
      .then((r: HealthResponse) => setHealth(r.status === 'ok' ? 'online' : 'offline'))
      .catch(() => setHealth('offline'))
  }, [])

  useEffect(() => {
    void supabase.auth.getSession().then(({ data }) => setAuthSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, session) => {
      setAuthSession(session)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  const signInWithGoogle = useCallback(async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/` },
    })
  }, [])

  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
  }, [])

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar
        health={health}
        authSession={authSession}
        onSignIn={() => void signInWithGoogle()}
        onSignOut={() => void signOut()}
      />
      <Routes>
        <Route path="/" element={<ResearchPage authSession={authSession} />} />
        <Route path="/resources" element={<ResourcesPage authSession={authSession} />} />
        <Route path="/agents" element={<AgentsPage authSession={authSession} />} />
      </Routes>
    </div>
  )
}

export default App
