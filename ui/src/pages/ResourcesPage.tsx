import { useCallback, useEffect, useState } from 'react'
import { Upload } from 'lucide-react'
import type { Session } from '@supabase/supabase-js'
import { deleteRagResource, listRagResources, uploadRagResource } from '@/api/client'
import { ResourceTable } from '@/components/resources/ResourceTable'
import { UploadFileDialog } from '@/components/resources/UploadFileDialog'
import { Button } from '@/components/ui/button'
import type { RagResource } from '@/types'

export function ResourcesPage({ authSession }: { authSession: Session | null }) {
  const [resources, setResources] = useState<RagResource[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)

  const load = useCallback(async () => {
    if (!authSession?.access_token) return
    setLoading(true)
    try {
      const { resources: data } = await listRagResources(authSession.access_token)
      setResources(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resources.')
    } finally {
      setLoading(false)
    }
  }, [authSession?.access_token])

  useEffect(() => {
    void load()
  }, [load])

  const handleUpload = async (file: File) => {
    if (!authSession?.access_token) return
    try {
      await uploadRagResource(file, authSession.access_token)
      await load()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload resource.')
      throw err
    }
  }

  const handleDelete = async (id: string) => {
    if (!authSession?.access_token) return
    try {
      await deleteRagResource(id, authSession.access_token)
      setResources((prev) => prev.filter((r) => r.resource_id !== id))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete resource.')
    }
  }

  return (
    <main className="max-w-screen-lg mx-auto px-4 py-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Resources</h1>
        {authSession && (
          <Button size="sm" onClick={() => setUploadOpen(true)}>
            <Upload size={14} />
            Upload file
          </Button>
        )}
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
      {!authSession ? (
        <p className="text-muted-foreground text-sm">Sign in to manage your resources.</p>
      ) : loading ? (
        <p className="text-muted-foreground text-sm">Loading...</p>
      ) : (
        <ResourceTable resources={resources} onDelete={handleDelete} />
      )}
      <UploadFileDialog open={uploadOpen} onOpenChange={setUploadOpen} onUpload={handleUpload} />
    </main>
  )
}
