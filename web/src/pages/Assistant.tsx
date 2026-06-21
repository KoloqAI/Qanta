import { useState, useRef, useEffect } from 'react'
import { apiFetch, apiMutate } from '../lib/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  tool_calls?: { name: string; status: string }[]
  staged_actions?: { id: string; action: string; params: Record<string, unknown>; status: string }[]
}

export function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const resp = await apiFetch<{ message: Message }>('/api/assistant/messages', {
        method: 'POST',
        body: JSON.stringify({ content: input }),
      })
      setMessages(prev => [...prev, resp.message ?? {
        id: crypto.randomUUID(), role: 'assistant',
        content: 'I can help you research strategies, analyze tickers, and manage your deployments. What would you like to explore?',
      }])
    } catch {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(), role: 'assistant',
        content: 'I can help you research strategies, analyze tickers, and manage your deployments. What would you like to explore?',
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmAction = async (actionId: string) => {
    try {
      await apiMutate(`/api/assistant/actions/${actionId}/confirm`)
      setMessages(prev =>
        prev.map(msg => ({
          ...msg,
          staged_actions: msg.staged_actions?.map(sa =>
            sa.id === actionId ? { ...sa, status: 'confirmed' } : sa
          ),
        }))
      )
    } catch {
      // keep staged action visible so user can retry
    }
  }

  const handleCancelAction = async (actionId: string) => {
    try {
      await apiMutate(`/api/assistant/actions/${actionId}/cancel`)
      setMessages(prev =>
        prev.map(msg => ({
          ...msg,
          staged_actions: msg.staged_actions?.map(sa =>
            sa.id === actionId ? { ...sa, status: 'cancelled' } : sa
          ),
        }))
      )
    } catch {
      // keep staged action visible so user can retry
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-hairline p-4">
        <h1 className="font-display text-xl text-ink">Assistant</h1>
        <p className="text-sm text-muted">Research strategies, analyze data, manage deployments</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-3">
              <p className="text-lg text-muted">How can I help you today?</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {['Scan for momentum candidates', 'Analyze AAPL technicals', 'Show my portfolio'].map(s => (
                  <button key={s} onClick={() => setInput(s)}
                    className="px-3 py-1.5 text-sm border border-hairline rounded-lg text-muted hover:text-ink hover:border-indigo transition">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[75%] rounded-lg px-4 py-2 ${
              msg.role === 'user' ? 'bg-indigo text-white' : 'bg-surface border border-hairline text-ink'
            }`}>
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              {msg.tool_calls && msg.tool_calls.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {msg.tool_calls.map((tc, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-indigo/10 text-indigo">{tc.name}</span>
                  ))}
                </div>
              )}
              {msg.staged_actions && msg.staged_actions.length > 0 && (
                <div className="mt-2 space-y-2">
                  {msg.staged_actions.map(sa => (
                    <div key={sa.id} className="border border-amber rounded-lg p-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-amber">{sa.action}</span>
                        {sa.status === 'pending' ? (
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleConfirmAction(sa.id)}
                              className="text-xs px-2 py-0.5 rounded bg-gain/10 text-gain hover:bg-gain/20"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => handleCancelAction(sa.id)}
                              className="text-xs px-2 py-0.5 rounded bg-loss/10 text-loss hover:bg-loss/20"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            sa.status === 'confirmed' ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss'
                          }`}>
                            {sa.status}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-surface border border-hairline rounded-lg px-4 py-2">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-muted rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-muted rounded-full animate-bounce [animation-delay:0.1s]" />
                <span className="w-2 h-2 bg-muted rounded-full animate-bounce [animation-delay:0.2s]" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-hairline p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            placeholder="Ask anything..."
            className="flex-1 px-4 py-2 bg-inset border border-hairline rounded-lg text-sm text-ink placeholder:text-faint focus:outline-none focus:border-indigo"
          />
          <button onClick={send} disabled={loading || !input.trim()}
            className="px-4 py-2 bg-indigo text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-indigo/90 transition">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
