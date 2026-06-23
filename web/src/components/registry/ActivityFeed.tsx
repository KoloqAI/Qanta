import { useEffect, useRef } from 'react'
import type { JobEvent } from '../../lib/jobEvents'
import type { StreamStatus } from '../../hooks/useJobStream'
import { cn } from '../../lib/cn'

interface ActivityFeedProps {
  events: JobEvent[]
  status: StreamStatus
  error: string | null
}

function StepIcon({ eventStatus }: { eventStatus?: string }) {
  if (eventStatus === 'done')
    return <span className="text-gain text-xs leading-none">&#10003;</span>
  if (eventStatus === 'failed')
    return <span className="text-loss text-xs leading-none">&#10007;</span>
  return (
    <span className="inline-block h-3 w-3 rounded-full border-2 border-indigo border-t-transparent animate-spin motion-reduce:animate-none" />
  )
}

function formatTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

export function ActivityFeed({ events, status, error }: ActivityFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el || userScrolledRef.current) return
    el.scrollTop = el.scrollHeight
  }, [events.length])

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    userScrolledRef.current = el.scrollHeight - el.scrollTop - el.clientHeight > 40
  }

  if (status === 'idle') return null

  const latestFunnel = [...events].reverse().find(e => e.funnel)?.funnel

  return (
    <div className="flex flex-col border-t border-hairline min-h-0 shrink-0 max-h-[33%]">
      {/* Feed header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-inset">
        <span className="text-xs font-medium text-muted">Activity</span>
        <span
          className={cn(
            'text-[10px] px-1.5 py-0.5 rounded',
            status === 'streaming' && 'bg-indigo/10 text-indigo',
            status === 'done' && 'bg-gain/10 text-gain',
            status === 'error' && 'bg-loss/10 text-loss',
            (status === 'connecting' || status === 'reconnecting') &&
              'bg-amber/10 text-amber',
          )}
        >
          {status === 'streaming'
            ? 'Running'
            : status === 'done'
              ? 'Complete'
              : status === 'error'
                ? 'Failed'
                : status === 'reconnecting'
                  ? 'Reconnecting...'
                  : 'Connecting...'}
        </span>
      </div>

      {/* Live exploration funnel counters */}
      {latestFunnel && (
        <div className="shrink-0 grid grid-cols-4 gap-2 px-4 py-2 border-b border-hairline">
          {(
            [
              ['Trials', latestFunnel.trials],
              ['Backtested', latestFunnel.backtested],
              ['Validated', latestFunnel.validated],
              ['Survivors', latestFunnel.survivors],
            ] as const
          ).map(([label, count]) => (
            <div key={label} className="text-center">
              <div className="font-mono text-sm text-ink">{count}</div>
              <div className="text-[10px] text-muted">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Scrollable event list */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto min-h-0"
      >
        {events.length === 0 && status === 'connecting' && (
          <div className="px-4 py-6 text-center">
            <span className="text-xs text-muted">Waiting for events...</span>
          </div>
        )}

        <div className="px-4 py-2 space-y-1">
          {events
            .filter(e => e.type !== 'progress' || e.label)
            .map((event, i) => {
              const resolved =
                event.status ??
                (event.type === 'run_finished'
                  ? 'done'
                  : event.type === 'run_error'
                    ? 'failed'
                    : undefined)

              return (
                <div key={i} className="flex items-start gap-2 py-1">
                  <div className="mt-0.5 w-4 shrink-0 flex justify-center">
                    <StepIcon eventStatus={resolved} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-ink truncate">
                        {event.label ?? event.type.replace(/_/g, ' ')}
                      </span>
                      {event.progress && (
                        <span className="text-[10px] font-mono text-faint shrink-0">
                          {event.progress.current}/{event.progress.total}
                        </span>
                      )}
                    </div>
                    {event.tool_name && (
                      <span className="text-[10px] text-faint">
                        {event.tool_name}
                      </span>
                    )}
                    {event.tool_result && (
                      <p className="text-[10px] text-muted mt-0.5 truncate">
                        {event.tool_result}
                      </p>
                    )}
                  </div>
                  <span className="text-[10px] text-faint shrink-0 font-mono">
                    {formatTime(event.timestamp)}
                  </span>
                </div>
              )
            })}
        </div>

        {/* Scan results rendered at the end of the feed */}
        {status === 'done' &&
          (() => {
            const last = [...events].reverse().find(e => e.candidates)
            if (!last?.candidates?.length) return null
            return (
              <div className="px-4 py-2 border-t border-hairline">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-muted">
                    {last.candidates.length} candidate
                    {last.candidates.length !== 1 ? 's' : ''}
                  </span>
                  {last.is_sample_fallback && (
                    <span className="text-[10px] px-1 py-0.5 rounded bg-amber/20 text-amber">
                      Sample data
                    </span>
                  )}
                </div>
                {last.candidates.slice(0, 10).map(c => (
                  <div
                    key={c.ticker}
                    className="flex justify-between text-xs py-0.5"
                  >
                    <span className="font-mono text-ink">{c.ticker}</span>
                    <span className="font-mono text-muted">
                      {c.fit_score.toFixed(4)}
                    </span>
                  </div>
                ))}
                {last.candidates.length > 10 && (
                  <span className="text-[10px] text-faint">
                    +{last.candidates.length - 10} more
                  </span>
                )}
              </div>
            )
          })()}
      </div>

      {/* Error banner */}
      {status === 'error' && error && (
        <div className="shrink-0 px-4 py-2 border-t border-hairline bg-loss/5">
          <p className="text-xs text-loss">{error}</p>
        </div>
      )}

      {/* Reconnecting banner */}
      {status === 'reconnecting' && (
        <div className="shrink-0 px-4 py-2 border-t border-hairline bg-amber/5">
          <p className="text-xs text-amber">Connection lost. Reconnecting...</p>
        </div>
      )}
    </div>
  )
}
