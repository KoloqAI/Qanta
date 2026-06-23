# 10 — Theming & UI Tokens

The hi-fi mockups in `design/` are the visual source of truth. Build the frontend from these tokens.

## Theming mechanism
- All colors resolve through CSS variables. The active theme is a `data-theme` attribute on the document root.
- Three settings: **system** (default — follows `prefers-color-scheme`), **light**, **dark**.
- Light tokens live in `:root`. Dark tokens override under `html[data-theme="dark"]` and under a
  `@media (prefers-color-scheme: dark)` block scoped to `html:not([data-theme="light"]):not([data-theme="dark"])`
  so "system" resolves correctly.
- Persisted as a **user preference** (`user_settings.appearance.theme`), surfaced at Settings → Appearance,
  default `system`. Apply the stored value to the root **before first paint** (inline head script reading the
  server-provided preference) to avoid a flash-of-wrong-theme.

## Design tokens
Direction: a precision *instrument*, not a casino — calm, exact, honest about uncertainty.

Type roles: display `Space Grotesk` (500); body `Inter` (400/500); data/numerals `JetBrains Mono`
(tabular) — every number renders in mono. Heading scale 20/18/16; body 14; captions 11–12.

| Token | Light | Dark |
|-------|-------|------|
| paper (page) | `#F5F6F4` | `#14171B` |
| surface | `#FFFFFF` | `#1B2025` |
| inset | `#F2F3F0` | `#20252B` |
| ink (text) | `#1B2127` | `#E9EBE7` |
| muted | `#6A7178` | `#9AA1A8` |
| faint | `#9AA0A4` | `#69707A` |
| hairline | `#E4E6E2` | `#2A3038` |
| indigo (accent) | `#34408B` | `#8A95E0` |
| indigo-soft | `#ECEEF7` | `#232B45` |
| amber (caution) | `#B07A1E` | `#D9A441` |
| gain (muted) | `#2F6B4F` | `#5FB088` |
| loss (muted) | `#9C3B33` | `#D7726A` |

P&L color is deliberately muted — the product de-emphasizes dopamine numbers. Accent (indigo) is the one
strong color; amber marks uncertainty/caution.

## Signature component — confidence interval bar
A horizontal gauge per (target, horizon): an axis 0–100%, a shaded band for the 90% credible interval, a
marker at the point estimate, a dashed amber tick at the gate threshold, mono % label. It is the product's
visual identity and must appear on Strategy Detail (review) and anywhere a confidence is shown. Never render
a confidence as a bare triumphant number.

## Component inventory (build with Tailwind + shadcn/ui)
Stat card (mono value, muted label) · panel (hairline border, radius-lg) · pill/status chip · segmented
control · metric grid · nav rail (grouped) · top status bar (mode, kill-switch, data feed, search budget) ·
metric pass-chips · red-team list · decision bar (reason + reject + approve) · assistant message + tool-call
chip + staged-action confirm card · equity/price chart (lightweight-charts) · analytics charts (Recharts) ·
**master-detail panel** (list + docked right panel with URL-driven selection; mobile slide-over variant) ·
**agent/job activity feed** (step stream) — ordered chronological step list with status icon, label,
timestamp, optional progress count, and collapsible tool-call detail; reuses the tool-call-chip pattern
from the Assistant screen; renders AG-UI-style events from `/ws/jobs/{id}`.

## States (every data view)
empty (an invitation to act) · loading (skeleton) · partial · error/degraded (says what happened + how to
fix, in the interface's voice) · alert (kill-switch fired — loud). Copy: sentence case, active voice, named
by what the user controls. The button that says "Approve" produces a toast that says "Approved."

## Quality floor
Responsive to mobile; visible keyboard focus rings; `prefers-reduced-motion` respected; all displayed
numbers rounded; no hardcoded colors in components — only tokens, so the theme toggle works everywhere.
**Independent scroll regions / sticky sidebar**: the app shell uses a viewport-height flex layout
(`h-dvh`) with `min-h-0` on flex children so the sidebar, list column, and detail panel each have their
own `overflow-y:auto` — scrolling one never moves the others. AG-UI-style event rendering in the
activity feed reuses the tool-call-chip pattern (status icon + label + detail).
