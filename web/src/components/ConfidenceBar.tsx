interface ConfidenceBarProps {
  value?: number
  lo?: number
  hi?: number
  C?: number
  C_lo?: number
  C_hi?: number
  threshold?: number
  label?: string
}

export function ConfidenceBar(props: ConfidenceBarProps) {
  const c = (props.value ?? props.C ?? 0) * 100
  const cLo = (props.lo ?? props.C_lo ?? 0) * 100
  const cHi = (props.hi ?? props.C_hi ?? 1) * 100
  const threshold = (props.threshold ?? 0.5) * 100

  return (
    <div className="w-full">
      {props.label && <p className="text-xs text-muted mb-1">{props.label}</p>}
      <div className="relative h-6 bg-inset rounded">
        <div
          className="absolute h-full bg-indigo/20 rounded"
          style={{ left: `${cLo}%`, width: `${cHi - cLo}%` }}
        />
        <div
          className="absolute h-full w-0.5 bg-indigo"
          style={{ left: `${c}%` }}
        />
        <div
          className="absolute h-full w-0.5 border-l border-dashed border-amber"
          style={{ left: `${threshold}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="font-mono text-xs text-faint">0%</span>
        <span className="font-mono text-xs text-ink">{c.toFixed(1)}%</span>
        <span className="font-mono text-xs text-faint">100%</span>
      </div>
    </div>
  )
}
