# 09 — API, Data Model & Tool Catalog

## REST / WebSocket surface
All non-public routes require an authenticated session (`current_user`). Mutating routes need CSRF.
Long jobs return a `job_id` and stream progress over WS.

```
Auth
  POST   /auth/login            POST /auth/logout         GET /auth/me
  POST   /auth/register         POST /auth/passkey/*       (single-user: register gated)
Strategies & research
  POST   /research/runs                  # start a research run (goal or ticker) -> job_id
  GET    /research/runs/{id}              # status + proposed candidates
  GET    /strategies                      # registry list (filter by state/family/ticker)
  GET    /strategies/{id}                 # detail (versions, validation report, deployments)
  POST   /strategies/{id}/validate        # run the gauntlet -> job_id
  POST   /strategies/{id}/approve         # body: {approved: bool, reason: str}; creates Approval (risk_increasing).
                                         # Rejection reuses this endpoint with approved:false — there is no /reject route.
Deployments
  POST   /deployments                     # body: {strategy_version_id, mode, guardrails}; live needs Approval (risk_increasing)
  GET    /deployments                     # active + historical
  POST   /deployments/{id}/pause          # risk_reducing
  POST   /deployments/{id}/flatten        # risk_reducing
  POST   /deployments/{id}/retire         # risk_reducing
  POST   /deployments/{id}/promote        # paper -> live (risk_increasing; needs gate)
Book & analytics
  GET    /portfolio                       # equity, exposure, aggregate stats, allocation
  GET    /performance                     # history, realized-vs-expected, calibration
  GET    /monitor                         # live deployment cards + kill-switch status
Evolution
  GET    /evolution/digest                # promotions/retirements/survivors/proposals + meta-lockbox
  POST   /evolution/proposals/{id}/decide # approve/reject Tier-3 (risk_increasing)
Assistant
  POST   /assistant/messages              # NL turn; returns text + grounded data + staged actions
  POST   /assistant/actions/{id}/confirm  # confirm a staged risk_increasing action
Library & sandbox (doc 13)
  GET    /library                         # archetypes + status
  GET    /library/{id}                    # detail + exploration funnel
  POST   /library/{id}/scan               # {universe?, as_of?} -> ranked candidates
  POST   /library/{id}/explore            # {budget, param_grid?} -> job_id (ledger-tracked sweep)
  POST   /backtest                        # {source: spec|{archetype_id,params}|strategy_version_id, tickers[], start, end, timeframe, mode} -> job_id
Settings
  GET/PUT /settings/connections /settings/models /settings/risk
          /settings/validation /settings/tools /settings/workflows /settings/portfolio
          /settings/notifications /settings/account /settings/appearance   # appearance: {theme: system|light|dark}

  All settings GET endpoints return **wrapped objects**, not bare arrays. The frontend `queryFn`
  for each tab is responsible for unwrapping. Shape reference:
    /settings/connections  → {broker, data, redis, database}
    /settings/models       → {tiers: {local|mid|frontier: {primary, fallback}}}
    /settings/risk         → {guardrails: {...caps...}, kill_switch_active: bool}
    /settings/validation   → {thresholds: {deflated_sharpe_min, pbo_max, min_trades, ...}}
    /settings/tools        → {tools: [{name, description, permission}]}  # cost_tier planned, not yet implemented
    /settings/workflows    → {workflows: []}
    /settings/portfolio    → {allocation: {method, cash_buffer_pct, max_strategies}, caps: {...}}
    /settings/notifications→ {channels: [{type, enabled}], severity_routing, quiet_hours}
    /settings/appearance   → {theme: "system"|"light"|"dark"}
  Do NOT pass the raw apiFetch promise as queryFn — always extract the payload in an async wrapper.
WS
  /ws/jobs/{id}   /ws/monitor   /ws/assistant

  Transport: Redis Streams.  The worker XADD's events to a Redis Stream
  keyed ``job:{id}:events`` (MAXLEN ~1000, TTL 1 h).  The WS relay in the
  API process XREAD BLOCKs from id "0" so late-connecting clients replay
  the full history.  For legacy jobs that never publish a stream the XREAD
  times out every 5 s and the relay sends a heartbeat — identical to the
  old heartbeat-only fallback.  No in-process event bus; worker and API
  are fully decoupled via Redis.

  /ws/jobs/{id} event vocabulary (consumed by the Registry activity feed):
  The client normalizes raw WS messages into AG-UI-style events via `web/src/lib/jobEvents.ts`:
    run_started    — job accepted; lifecycle begins
    step_started   — a named step begins (label, step_id)
    step_finished  — a step completes (status: done | failed, optional tool_result)
    tool_result    — tool-call detail (tool_name, tool_result text)
    progress       — incremental count update (progress: {current, total})
    run_finished   — terminal success; may include candidates[] (Scan) or funnel{} (Explore)
    run_error      — terminal failure (error message)

  Scan emits: run_started → step events for universe filter, bar fetch, scan eval, ranking →
    run_finished with {candidates: [{ticker, fit_score, archetype, family}], is_sample_fallback}.

  Explore (task ``run_explore``) emits: run_started → step_started/step_finished pairs for
    universe scan, per-ticker backtest, and per-ticker validate → progress events carrying a live
    funnel ``{trials, backtested, validated, survivors}`` → run_finished with final funnel +
    survivor links. Funnel counters are streamed as live ``progress`` events (field: ``funnel``)
    so the activity feed can update in real time.
```

## Data model (column level)
```
users(id pk, email uniq, cred_hash, created_at, ...)
sessions(id pk, user_id fk, token_hash, expires_at, created_at)
user_settings(user_id fk, appearance jsonb, risk jsonb, models jsonb, ...)   # appearance.theme
strategies(id pk, user_id fk, name, domain, family, status, created_at)
strategy_versions(id pk, strategy_id fk, version int, rules jsonb, thesis text,
                  dsl_version, author jsonb, state, created_at)
research_runs(id pk, user_id fk, goal text, mode, trials_count int, status, created_at)
trials(id pk, research_run_id fk, params jsonb, in_sample_sharpe float, spec_hash)
backtest_runs(id pk, strategy_version_id fk, window jsonb, sharpe float, max_dd float,
              net_edge float, frictionless_edge float, equity_curve jsonb, n_trades int)
validation_reports(id pk, strategy_version_id fk, deflated_sharpe float, pbo float nullable,
                   deg_slope float nullable, peer_hit float, n_eff int, passed bool,
                   confidence_curve jsonb, detail jsonb, created_at)
                   -- pbo/deg_slope nullable: NULL = single-config (PBO undefined)
deployments(id pk, strategy_version_id fk, mode enum(paper,live), status, guardrails jsonb,
            capital_budget float, started_at, ended_at)
orders(id pk, deployment_id fk, symbol, side, qty float, type, status, ts)
fills(id pk, order_id fk, price float, qty float, ts)
approvals(id pk, user_id fk, strategy_version_id fk, approved bool, reason text, ts)
audit_log(id pk, user_id fk, actor enum(user,agent,system,assistant), action, subject_type,
          subject_id, payload jsonb, ts)                 # immutable
search_ledger(id pk, spec_hash, hypothesis_family, data_window jsonb, model_version,
              result_metrics jsonb, ts)                  # append-only, feeds n_eff
calibration(id pk, validation_report_id fk, claimed_c float, target_r float, horizon int,
            realized_outcome bool, resolved_at)           # confidence calibration
evolution_runs(id pk, tier int, summary jsonb, meta_lockbox_result jsonb, ts)
-- PLANNED (not yet implemented): currently loaded in-memory from config/library/*.yaml on startup.
-- When this table lands, add a re-seed / template-format migration to populate it from the
-- current YAML files (which now use {param} placeholders + default: values).
library_archetypes(id pk, name, family, horizon, thesis, template jsonb, scan jsonb,
                   param_grid jsonb, source enum(seed,evolved), status, created_at)
exploration_runs(id pk, archetype_id fk, budget_spent, trials int, survivors int, ts)
```
Scope every user-owned row by `user_id` (single-user now, multi-user-ready).

## Tool catalog (registered tools; `permission` governs who/what may invoke)
| Tool | Permission | In → Out |
|------|------------|----------|
| `universe_scan` | read | {archetype_id?, as_of?} → {candidates: [{ticker, fit_score, archetype, family}], is_sample_fallback: bool}. Builds universe via Polygon grouped-daily → liquidity filter (median dollar-vol, trailing window) → DSL scan evaluation → ranked results. Sample fallback when no real provider configured. |
| `technical_analysis` | read | ticker, indicators → analysis (uses DSL features) |
| `characterize_ticker` | read | ticker → regime/behavior profile + stats |
| `news_search` | read | **planned** — ticker/window → news items (requires news module). Not yet implemented. |
| `author_strategy` | read | thesis + intent → DSL spec (LLM-authored, DSL type-check gate applied). Falls back to template with `is_fallback_template: true` when no LLM configured. |
| `backtest` | read | spec, window → BacktestResult |
| `validate` | read | spec, n_eff?, competing_returns? → ValidationReport. Gauntlet incl. peer-hit gate and multi-config PBO (via CSCV). When `competing_returns` (T×N matrix, N≥2) is provided, computes real PBO over the param-grid configs (columns deduped — identical return vectors collapsed); otherwise PBO=None (single-config: gate skipped, DSR+n_eff carry deflation). Survivor dicts include `n_configs_swept` and `n_configs_distinct`. `gates_version` tracks gate-set evolution; stale reports blocked from approval/deployment. |
| `peer_test` | read | {spec, peers?, as_of?} → {peer_hit, n_peers_tested, n_peers_with_edge, sufficient, details}. Backtests spec on correlation-based peers (point-in-time). Peers auto-selected via return correlation if not explicit. Fails closed when peer data is insufficient. |
| `query_book` | read | — → portfolio/positions/exposure |
| `query_performance` | read | **planned** — filter → history, realized-vs-expected, calibration. Not yet implemented. |
| `pause_deployment` `flatten_deployment` | risk_reducing | deployment_id → ack (assistant may execute; fail-safe) |
| `halt_deployment` | risk_reducing | **planned** — not yet registered; use `pause_deployment` + `flatten_deployment`. |
| `deploy_strategy` `approve_strategy` | risk_increasing | … → STAGED only; executed by deterministic code after an Approval; never invoked by an LLM |
| `promote_to_live` `set_guardrail` `place_order` | risk_increasing | **planned** — not yet registered. Will be STAGED-only like deploy/approve. |

12 tools registered as of `gates_version` 4.

### MarketDataProvider interface
```
bars(symbol, start, end, timeframe, as_of) -> DataFrame
universe(as_of) -> list[str]
filtered_universe(as_of, min_price, min_dollar_volume, cap) -> list[str]
reconstitution_events(index, as_of, start?, end?) -> list[{symbol, index, action, preliminary_list_date, final_list_date, effective_date}]
earnings_events(symbol, start, end, as_of?) -> list[{symbol, announce_date, session: BMO|AMC}]
```
`reconstitution_events` is **point-in-time**: events are only revealed once `as_of >= final_list_date`.
`SampleDataProvider` returns a deterministic synthetic calendar (Russell 2000, two years of adds/deletes).
`PolygonDataProvider` raises `NotImplementedError` — Polygon OHLCV does not include index membership
changes; a dedicated vendor feed (FTSE Russell, ICE, or data vendor) must be wired.

`earnings_events` is **point-in-time**: announcements only returned when `announce_date <= as_of`.
Each event includes a `session` flag (`BMO` = before market open, `AMC` = after market close) that
determines which bar shows the reaction.  `SampleDataProvider` returns a deterministic synthetic
quarterly earnings calendar (all sample universe tickers + delisted names, 2022-2025).
`PolygonDataProvider` raises `NotImplementedError` — requires a financials/reference subscription
or a dedicated earnings-calendar vendor.

Workflows are declarative pipelines over these tools (e.g., evolution T2: `universe_scan → author_strategy → backtest(param grid) → validate(competing_returns)`), runnable on a schedule without an interactive agent.