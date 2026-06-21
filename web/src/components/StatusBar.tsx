export function StatusBar() {
  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-hairline bg-surface px-4 py-2">
      <div className="flex items-center gap-4">
        <span className="font-display text-sm text-ink font-medium">Quanta</span>
        <span className="text-xs text-muted">Paper</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-gain">Data OK</span>
        <span className="text-xs text-muted">Kill switch: off</span>
      </div>
    </header>
  )
}
