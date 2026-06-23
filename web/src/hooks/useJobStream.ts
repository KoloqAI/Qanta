import { useEffect, useRef, useState } from 'react'
import { subscribeWs } from '../lib/ws'
import { normalizeJobEvent, type JobEvent } from '../lib/jobEvents'

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error' | 'reconnecting'

export function useJobStream(jobId: string | null) {
  const [events, setEvents] = useState<JobEvent[]>([])
  const [status, setStatus] = useState<StreamStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const terminalRef = useRef(false)

  useEffect(() => {
    if (!jobId) {
      setEvents([])
      setStatus('idle')
      setError(null)
      terminalRef.current = false
      return
    }

    setEvents([])
    setStatus('connecting')
    setError(null)
    terminalRef.current = false

    const sub = subscribeWs(
      `/ws/jobs/${jobId}`,
      (raw) => {
        const event = normalizeJobEvent(raw as Record<string, unknown>)
        setEvents(prev => [...prev, event])
        if (event.type === 'run_started') setStatus('streaming')
        if (event.type === 'run_finished') {
          setStatus('done')
          terminalRef.current = true
        }
        if (event.type === 'run_error') {
          setStatus('error')
          setError(event.error ?? 'Job failed')
          terminalRef.current = true
        }
      },
      (wsStatus) => {
        if (wsStatus === 'disconnected' && !terminalRef.current) {
          setStatus('reconnecting')
        }
      },
    )

    return () => sub.unsubscribe()
  }, [jobId])

  return { events, status, error }
}
