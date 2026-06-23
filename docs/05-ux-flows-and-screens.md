# 05 — UX Flows & Screens

Platform: desktop-first responsive web SPA. Wireframes for the three hero screens (Portfolio, Assistant,
Strategy Detail review state) were produced in design and should be treated as the layout source of truth;
hi-fi styling is a later frontend-design pass.

## Flows
**F1 — Research → Validated Strategy → Deployment (spine).** Entry: (A) single-ticker deep-dive or
(B) universe scan → research agent (thesis + DSL spec) → backtest + validation gauntlet (trials logged) →
deflated confidence → human review (evidence vs counter-evidence) → approve → deploy to paper → promote
gate → live → monitor. Branches: entry mode; pass/fail; approve/reject; promote/hold; PDT block.
Failure paths each recover (never dead-end): no thesis (explain/reframe), validation fail (show which
gate + why, loop to refine), reject (reason feeds agent), PDT block (offer swing), paper divergence
(block promotion), kill-switch fired (alert + reset). Paper is always required before live.

**F2 — Monitor → Intervene.** Dashboard → drill a deployment → pause/flatten/retire. Alert states:
kill-switch fired, data feed degraded, decay flagged.

**F3 — Evolution review.** Loop runs → digest (promotions/retirements FYI; discovered survivors;
Tier-3 proposals) → user approves/rejects capability changes with meta-lockbox results shown. Cannot
relax a guardrail or self-deploy.

## Screen map & navigation
Pre-app: **Login**. App shell: persistent top bar (account mode, kill-switch status, data feed, search
budget) pinned at top + **grouped left sidebar fixed full-height** (sticky, scrolls independently of
content). The content area owns its own scroll region; scrolling content never moves the sidebar or top
bar. Three independent scroll regions app-wide: **sidebar | content area** (on the Registry screen this
further splits into **list column | detail panel**, each with independent overflow). Strategy Detail is
the shared hub reached by drilling in (not a sidebar item).

Sidebar groups → screens:
- Work: **Assistant** (also a slide-over on every screen)
- Your Book: **Portfolio** (home/overview), **Monitor** (live ops + intervention), **Performance & History** (track record + calibration)
- Strategies: **Review Queue** (pending approvals), **Registry** (all strategies + templates)
- System: **Evolution** (digest + Tier-3 approvals), **Settings** (Connections, Models & Routing, Risk & Guardrails, Validation Thresholds, Portfolio & Allocation, Tools & Modules, Workflows, Notifications, Appearance, **Account**)
- Shared hub: **Strategy Detail** (state-aware: review decision when pending; live section when deployed)
- Overlay: **Deploy Config** (modal over Strategy Detail on approve)

## Per-screen specs
**Login** — auth entry; email/passkey; error states (bad creds, locked); leads to first-run setup if unconfigured, else Portfolio.

**Portfolio (home)** — account-level now + aggregate stats. Top: stat cards (total equity, day P&L, period return, live Sharpe, max DD, win rate) + time-range. Middle: portfolio equity curve. Lower: allocation & exposure vs limits | active deployments mini-list (→ Monitor). Glanceable; routes out, no per-strategy intervention here. (See wireframe.)

**Assistant** — grounded chat; renders real app data inline; tool-call activity chips; read + risk-reducing actions execute; risk-increasing actions show a stage-and-confirm card; composer. Full-screen + slide-over. (See wireframe.)

**Strategy Detail (shared hub)** — header (name, version, state chip, ticker) + section switch (Overview/Validation/Live). Review state: evidence panel (equity curve, confidence-vs-target, metric pass-chips, peer test, thesis) beside counter-evidence panel (red-team, worst-case Monte Carlo, skew/regime notes); decision bar (reason field + Reject + Approve; Approve opens Deploy Config). Live state: live P&L vs expected, positions, order log, guardrail health. (See wireframe for review state.) Action bar is state-driven: draft/backtested → Run Validation; validated → Approve & Deploy / Reject (Reject reuses the approve endpoint with approved:false); approved → Deploy Config modal; paper → Promote to Live / Pause / Flatten / Retire; live → Pause / Flatten / Retire. Approve, Deploy, and Promote are risk_increasing (confirm step); Pause/Flatten/Retire are risk_reducing.

**Review Queue** — list of validated-pending strategies (sidebar badge count); row → Strategy Detail review state.

**Monitor** — account P&L/exposure/kill-switch header; deployment cards (live P&L, positions, guardrail health, mini-curve) with Pause/Flatten/Retire; alert + degraded states.

**Performance & History** — portfolio results over time (realized, not backtest); all deployments past+present incl. closed/retired; realized-vs-expected per strategy; confidence calibration (do 80%s hit 80%); observability.

**Registry** — **master-detail layout**: the left column is the list, the right column is the detail
panel. Selection is URL-driven (`?sel=<id>&tab=...`) so it is deep-linkable and survives refresh. On
narrow/mobile viewports the right panel becomes a full-width slide-over (Radix/shadcn Sheet pattern).
Two tabs:

- **Instantiated** — browse/search all strategy versions across the lifecycle. Clicking a row opens
  the right panel with a state-aware summary: name, version, ticker(s), lifecycle state chip, key
  validation metrics (DSR, PBO, peer-hit, C_lo), confidence bar, and the **state-driven action bar**
  (draft/backtested → Run Validation; validated → Approve & Deploy / Reject; approved → Deploy Config;
  paper → Promote / Pause / Flatten / Retire; live → Pause / Flatten / Retire). Risk-increasing actions
  keep their stage-and-confirm step. An "Open full Strategy Detail →" link routes to the shared hub for
  the complete view — the panel is a quick-access summary, not a replacement.

- **Library** — the seed archetype catalog (doc 13). Cards grouped by family/theme, filterable by
  family + horizon. Clicking a card opens the right panel with archetype detail: full thesis, watched
  features, human-readable scan logic, param grid, exploration funnel
  (runs → trials → survivors), status/exclusion_reason, and the four actions **Run scan / Explore /
  Author from this / Open in Sandbox**.

The **lower region of the right panel** is a real-time **activity feed** (AG-UI-style event stream).
When the user clicks Scan or Explore, the panel subscribes to `/ws/jobs/{job_id}` and renders streamed
events as an ordered chronological step list: status icon, label, timestamp, optional progress count,
collapsible tool-call detail. For Explore, the exploration funnel counters (trials → backtested →
validated → survivors) update live and survivors link to the Review Queue. For Scan, candidates render
on completion with the `is_sample_fallback` banner when applicable. The info section, action bar, and
activity feed are three independent scroll regions within the panel — the action bar stays pinned so it
is never pushed off-screen. WS reconnect is handled with a degraded state banner.

**Backtest Sandbox** — hands-on manual backtest (doc 13): pick a registry version, a library archetype + params, or a pasted DSL spec; choose ticker(s), date range, timeframe, and mode (backtest-only | full gauntlet); see equity curve, trade list, metrics (plus DSR/PBO/confidence in gauntlet mode). Can promote to Research/Registry, never to live.

**Evolution** — digest of promotions/retirements; discovered survivors; Tier-3 capability proposals (approve/reject) with meta-lockbox results.

**Settings** — sub-nav: Connections (broker/data), Models & Routing (LiteLLM tiers + fallbacks), Risk & Guardrails (global limits), Validation Thresholds (pre-registered), Portfolio & Allocation (method, caps, cash buffer, max strategies), Tools & Modules (enable/disable, contracts), Workflows (declarative pipelines), Notifications (channels + per-severity routing + quiet hours), Appearance (theme: system/light/dark), Account (credentials, sessions, provider keys).

## States to implement for every data screen
empty · loading (skeleton) · partial · error/degraded · alert (kill-switch). The top bar always reflects
kill-switch + data-feed state. The **activity feed** adds streaming · done · error · reconnecting states
within the detail panel; WS reconnect shows a degraded banner and resubscribes to the same `job_id`.