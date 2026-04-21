import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  chatWithRagAgent,
  createRagAgent,
  deleteRagResource,
  listRagAgents,
  listRagResources,
  updateRagAgent,
  uploadRagResource,
} from '../api/client'
import type { RagAgent, RagChatMessage, RagResource } from '../types'

type RagAgentModeProps = {
  accessToken: string | null
}

type RagTab = 'resources' | 'agents' | 'chat'

export function RagAgentMode({ accessToken }: RagAgentModeProps) {
  const [tab, setTab] = useState<RagTab>('resources')
  const [resources, setResources] = useState<RagResource[]>([])
  const [agents, setAgents] = useState<RagAgent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  const [agentName, setAgentName] = useState('')
  const [agentDescription, setAgentDescription] = useState('')
  const [agentInstructions, setAgentInstructions] = useState('')
  const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([])
  const [savingAgent, setSavingAgent] = useState(false)

  const [selectedAgentId, setSelectedAgentId] = useState<string>('')
  const [chatSessionId, setChatSessionId] = useState<string | null>(null)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<RagChatMessage[]>([])
  const [chatting, setChatting] = useState(false)

  const loadAll = useCallback(async () => {
    if (!accessToken) return
    setLoading(true)
    try {
      const [resourceData, agentData] = await Promise.all([
        listRagResources(accessToken),
        listRagAgents(accessToken),
      ])
      setResources(resourceData.resources)
      setAgents(agentData.agents)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load RAG data.')
    } finally {
      setLoading(false)
    }
  }, [accessToken])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  const readyResources = useMemo(
    () => resources.filter((resource) => resource.state === 'ready'),
    [resources],
  )

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.agent_id === selectedAgentId) ?? null,
    [agents, selectedAgentId],
  )

  const toggleResource = useCallback((resourceId: string) => {
    setSelectedResourceIds((prev) =>
      prev.includes(resourceId) ? prev.filter((id) => id !== resourceId) : [...prev, resourceId],
    )
  }, [])

  const handleUpload = useCallback(async () => {
    if (!accessToken || !selectedFile) return
    setUploading(true)
    try {
      await uploadRagResource(selectedFile, accessToken)
      setSelectedFile(null)
      await loadAll()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload resource.')
    } finally {
      setUploading(false)
    }
  }, [accessToken, selectedFile, loadAll])

  const handleDeleteResource = useCallback(
    async (resourceId: string) => {
      if (!accessToken) return
      try {
        await deleteRagResource(resourceId, accessToken)
        await loadAll()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete resource.')
      }
    },
    [accessToken, loadAll],
  )

  const handleCreateAgent = useCallback(async () => {
    if (!accessToken || !agentName.trim()) return
    setSavingAgent(true)
    try {
      await createRagAgent(
        {
          name: agentName.trim(),
          description: agentDescription.trim(),
          system_instructions: agentInstructions.trim(),
          linked_resource_ids: selectedResourceIds,
        },
        accessToken,
      )
      setAgentName('')
      setAgentDescription('')
      setAgentInstructions('')
      setSelectedResourceIds([])
      await loadAll()
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent.')
    } finally {
      setSavingAgent(false)
    }
  }, [
    accessToken,
    agentName,
    agentDescription,
    agentInstructions,
    selectedResourceIds,
    loadAll,
  ])

  const handleAgentRelink = useCallback(
    async (agent: RagAgent) => {
      if (!accessToken) return
      try {
        await updateRagAgent(
          agent.agent_id,
          {
            linked_resource_ids: selectedResourceIds,
          },
          accessToken,
        )
        await loadAll()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update agent resources.')
      }
    },
    [accessToken, selectedResourceIds, loadAll],
  )

  const handleChat = useCallback(async () => {
    if (!accessToken || !selectedAgentId || !chatInput.trim()) return
    setChatting(true)
    try {
      const response = await chatWithRagAgent(
        selectedAgentId,
        chatInput.trim(),
        chatSessionId,
        accessToken,
      )
      setChatSessionId(response.session_id)
      setChatMessages(response.messages)
      setChatInput('')
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to chat with agent.')
    } finally {
      setChatting(false)
    }
  }, [accessToken, selectedAgentId, chatInput, chatSessionId])

  return (
    <section className="glass-panel card-spacing rag-mode-panel">
      <div className="rag-mode-header">
        <h2>RAG Agent</h2>
        <div className="rag-tabs" role="tablist" aria-label="RAG sections">
          <button type="button" className={`rag-tab ${tab === 'resources' ? 'is-active' : ''}`} onClick={() => setTab('resources')}>
            Resources
          </button>
          <button type="button" className={`rag-tab ${tab === 'agents' ? 'is-active' : ''}`} onClick={() => setTab('agents')}>
            Agents
          </button>
          <button type="button" className={`rag-tab ${tab === 'chat' ? 'is-active' : ''}`} onClick={() => setTab('chat')}>
            Chat
          </button>
        </div>
      </div>

      {error && <p className="error-banner">{error}</p>}

      {tab === 'resources' && (
        <div className="rag-tab-panel">
          <div className="rag-actions-row">
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
            <button
              type="button"
              className="submit-button"
              disabled={!selectedFile || uploading || !accessToken}
              onClick={() => void handleUpload()}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
            <button type="button" className="auth-button" onClick={() => void loadAll()} disabled={loading}>
              Refresh
            </button>
          </div>

          <ul className="rag-resource-list">
            {resources.map((resource) => (
              <li key={resource.resource_id} className="rag-resource-item">
                <div>
                  <strong>{resource.filename}</strong>
                  <p>
                    {(resource.byte_size / 1024).toFixed(1)} KB · <span className={`rag-state rag-state-${resource.state}`}>{resource.state}</span>
                  </p>
                  {resource.error_details && <p className="rag-error-details">{resource.error_details}</p>}
                </div>
                <button type="button" className="auth-button" onClick={() => void handleDeleteResource(resource.resource_id)}>
                  Delete
                </button>
              </li>
            ))}
            {resources.length === 0 && <li className="sessions-empty">No resources uploaded yet.</li>}
          </ul>
        </div>
      )}

      {tab === 'agents' && (
        <div className="rag-tab-panel">
          <div className="rag-agent-form">
            <input
              className="sessions-filter-input"
              value={agentName}
              onChange={(event) => setAgentName(event.target.value)}
              placeholder="Agent name"
            />
            <input
              className="sessions-filter-input"
              value={agentDescription}
              onChange={(event) => setAgentDescription(event.target.value)}
              placeholder="Description"
            />
            <textarea
              className="query-input"
              rows={4}
              value={agentInstructions}
              onChange={(event) => setAgentInstructions(event.target.value)}
              placeholder="System instructions"
            />
            <div className="rag-checkbox-list">
              {readyResources.map((resource) => (
                <label key={resource.resource_id} className="rag-checkbox-item">
                  <input
                    type="checkbox"
                    checked={selectedResourceIds.includes(resource.resource_id)}
                    onChange={() => toggleResource(resource.resource_id)}
                  />
                  <span>{resource.filename}</span>
                </label>
              ))}
              {readyResources.length === 0 && <p className="sessions-empty">No ready resources available.</p>}
            </div>
            <button
              type="button"
              className="submit-button"
              disabled={!agentName.trim() || savingAgent || !accessToken}
              onClick={() => void handleCreateAgent()}
            >
              {savingAgent ? 'Saving...' : 'Create Agent'}
            </button>
          </div>

          <ul className="rag-agent-list">
            {agents.map((agent) => (
              <li key={agent.agent_id} className="rag-agent-item">
                <div>
                  <strong>{agent.name}</strong>
                  <p>{agent.description || 'No description'}</p>
                  <p>{agent.linked_resource_ids.length} linked resources</p>
                </div>
                <button type="button" className="auth-button" onClick={() => void handleAgentRelink(agent)}>
                  Apply Selected Links
                </button>
              </li>
            ))}
            {agents.length === 0 && <li className="sessions-empty">No agents created yet.</li>}
          </ul>
        </div>
      )}

      {tab === 'chat' && (
        <div className="rag-tab-panel rag-chat-panel">
          <select
            className="sessions-filter-input"
            value={selectedAgentId}
            onChange={(event) => {
              setSelectedAgentId(event.target.value)
              setChatSessionId(null)
              setChatMessages([])
            }}
          >
            <option value="">Select an agent</option>
            {agents.map((agent) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name}
              </option>
            ))}
          </select>

          {selectedAgent && (
            <p className="followup-hint">
              {selectedAgent.description || 'Custom RAG agent'}
            </p>
          )}

          <div className="rag-chat-messages">
            {chatMessages.map((message) => (
              <div key={message.message_id} className={`rag-chat-message rag-chat-${message.role}`}>
                <strong>{message.role === 'user' ? 'You' : 'Agent'}:</strong> {message.content}
              </div>
            ))}
            {chatMessages.length === 0 && <p className="sessions-empty">No chat yet.</p>}
          </div>

          <div className="rag-chat-input-row">
            <textarea
              className="followup-textarea"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Ask your RAG agent a question..."
              rows={2}
            />
            <button
              type="button"
              className="submit-button"
              disabled={!chatInput.trim() || !selectedAgentId || chatting}
              onClick={() => void handleChat()}
            >
              {chatting ? 'Thinking...' : 'Send'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
