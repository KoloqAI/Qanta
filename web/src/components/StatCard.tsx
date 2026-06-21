interface StatCardProps {
  label: string
  value: string
  change?: string
  positive?: boolean
  className?: string
}

export function StatCard({ label, value, change, positive, className }: StatCardProps) {
  return (
    <div className="bg-surface border border-hairline rounded-lg p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className={`font-mono text-lg mt-1 ${className ?? 'text-ink'}`}>{value}</p>
      {change && (
        <p className={`font-mono text-xs mt-1 ${positive ? 'text-gain' : 'text-loss'}`}>
          {change}
        </p>
      )}
    </div>
  )
}
