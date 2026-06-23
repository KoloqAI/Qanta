# 06 — Build Sequence

Build in this order. Each milestone has an **acceptance gate** — a concrete, testable condition. Do not
advance past a red gate. This sequence de-risks fastest and lets the agent verify itself at each step.

## M0 — Foundation ✅
Scaffold the file tree (doc 02), `docker-compose` (api, worker, web, postgres, redis, ollama), config,
DI, Alembic schema (doc 02 data model), CI running `pytest`, and stubbed typed interfaces for every module.
**Gate:** `docker compose up` boots all services; `pytest` runs (empty/stub tests pass); a health endpoint returns 200.
**Status:** Done. Docker, config, DI, health endpoint, Alembic initial migration (001_initial_schema).

## M1 — Auth (M0 module) ✅
Users, argon2/passkey, server-side sessions (httpOnly+CSRF), `current_user` dependency, Login screen,
Account settings. Secrets vault wiring (broker/LLM keys never reach client/agent scope).
**Gate:** login works; mutating routes 401 without a session; secrets resolve from the vault; no secret appears in any client response (test asserts).
**Status:** Done. Argon2, server-side sessions, CSRF, current_user dep, Login screen. Bootstrap owner seeding via `OWNER_EMAIL`/`OWNER_PASSWORD` (lifespan, idempotent). `GET /auth/setup-status` routes frontend to Login vs Create Account. All SQLAlchemy `Enum()` columns fixed with `values_callable` to use lowercase DB values.

## M2 — Data + Backtest ✅
**Prerequisite:** confirm the historical data source delivers survivorship-free, point-in-time data incl. delisted names (vendor — Norgate / Polygon / Databento; see doc 12) before relying on it for the harness.
M1 Data (point-in-time, survivorship-free universe incl. delisted; feature computation; split/dividend adjustment + corporate-actions calendar) and M4 Backtest
(nautilus_trader backtest engine; cost model: spread+slippage+commission, next-bar/next-tick fills). No LLM, no broker. (Add PyBroker later only if you need faster vectorized sweeps.)
**Gate:** backtest a hand-written spec; frictionless vs net edge both reported; a seeded lookahead test is detected/blocked.
**Status:** Done. SampleDataProvider + PolygonDataProvider (real), FeatureComputer (16 indicators), LookaheadGuard, BacktesterImpl with cost model. Backtest engine is custom Python (same Backtester interface), nautilus_trader integration deferred to M9.

## M3 — Validation harness + verification suite (HIGHEST PRIORITY) ✅
M5: purged walk-forward (+embargo), DSR, PBO (CSCV), robustness battery, confidence metric, search-budget
ledger, lockbox. Ship the verification suite.
**Gate (must all pass):** PBO ≈ 0.5 on pure noise; PBO → 0 on seeded edge; DSR strictly decreases as N rises;
DSR lower for negative skew at equal Sharpe; cross-impl triangulation within tolerance; harness passes a
seeded known-good spec and fails a seeded known-overfit spec.
**Status:** Done. Walk-forward, DSR, PBO (CSCV), confidence (Beta-Binomial), 8 verification tests. Lockbox holdout (validate_with_lockbox) now enforced with 15% held-out slice.

## M4 — Strategy DSL ✅
core/dsl: primitive vocabulary, spec schema, parser + type-checker, deterministic interpreter (doc 03).
**Gate:** a valid spec type-checks and runs through M2+M3; a malformed/out-of-vocabulary spec is rejected at parse time (test).
**Status:** Done. Parser with 9 rules, interpreter with 16 primitives, all gate tests pass.

## M5 — Execution skeleton + guardrails on paper (SAFETY-CRITICAL) ✅
M6 ExecutionRuntime on nautilus_trader (same engine as M2 backtest → research-to-live parity) with PaperBroker / IBKRBroker (IB Gateway via IBeam, headless); M7 RiskGate as a mandatory pre-trade filter wrapping the engine; daily
kill-switch. No LLM in M6/M7. Our RiskGate is the safety authority — nautilus is only the executor.
Also in this milestone: `PortfolioRiskGate` (aggregate caps, runs after the per-order gate); broker-resident
bracket/OCO protection on every position + a heartbeat watchdog (dead-man's switch); the market-calendar
scheduler with EOD-flatten for intraday (doc 12).
**Gate (drills must fire):** stop-loss triggers and closes a position; an over-size order is rejected+logged;
gross-exposure cap rejects; a portfolio aggregate cap rejects; the broker-resident stop survives an engine
kill (position stays protected); intraday EOD-flatten fires before close; daily-drawdown kill-switch flattens
all + halts; a live deploy without a passing ValidationReport + Approval is refused; PDT block fires when intraday + <$25k.
**Status:** Done. PaperBroker with bracket orders + heartbeat watchdog. RiskGateImpl + PortfolioRiskGateImpl enforce all caps. DeploymentGate enforces ValidationReport+Approval for live. EODFlattenJob wired to MarketCalendar. LULD halt detection in RiskGate. 30+ safety drill tests pass. IBKRBroker deferred to M9.

## M6 — Tool registry + Research agent ✅
core/tools (registry, permission tiers); M2 Research (LangGraph agent via LiteLLM `LLMProvider`,
`ResearchDomain` = ShortTermEquityDomain, `StrategyAuthor`, red-team pass, trial logging). Read/research
tools only for the agent.
**Gate:** agent turns a goal/ticker into a DSL spec + thesis; trials are logged to the ledger; agent has no
execution tool (test asserts the agent cannot reach a risk_increasing tool or the broker).
**Status:** Done. 11 tools, permission tiers enforced, agent cannot access risk_increasing (tested). LiteLLMProvider with tier routing + stub fallback.

## M7 — UI + end-to-end paper loop ✅
Screens (doc 05): Login, Portfolio, Assistant, Strategy Detail (review+live), Review Queue, Monitor,
Performance & History, Registry, Evolution, Settings. Wire flow F1 end to end on paper. M8 Monitoring/Audit.
Assistant stage-and-confirm. Capital-budget allocation set in Deploy Config; Notifications module + Settings → Notifications (out-of-band alerts). Every screen implements empty/loading/partial/error/alert states.
**Gate:** propose → validate → review → approve → paper-trade → monitor works end to end; a capital budget is
assigned at deploy; a critical event (e.g. kill-switch) fires an out-of-band notification; assistant executes a
read + a risk-reducing action and STAGES a risk-increasing one (confirm required); audit log captures all of it.
**Status:** Done. All 9 pages, theme system, button handlers wired, API routes use real services. 4 E2E tests pass. Fixed: Settings → Workflows tab crash (`workflows queryFn` was forwarding the raw wrapped response object instead of extracting `d.workflows`; all settings queryFns must unwrap their response — see doc 09 response shape reference).

## M8 — Evolution loop ✅
Scheduled T1 promote/retire, T2 budgeted discover (ledger-fed deflation), T3 capability proposals;
meta-lockbox; Evolution screen.
**Gate:** loop promotes a proven strategy and retires a decayed one; T2 respects the budget and feeds N_eff;
a T3 change requires human approval and a non-degrading meta-lockbox result; nothing self-deploys.
**Status:** Done. T1 promote/retire, T2 budgeted discovery, T3 human-gated proposals, meta-lockbox.

## M9 — Hardening → optional live 🔜
Real-time data plan, corporate-actions + LULD-halt handling, broker-protection re-arm on reconnect, Terraform/AWS deploy, observability, calibration tracking live, repeat safety drills.
**Gate:** identical behavior local vs AWS; all M5 drills re-pass in the deploy target; calibration recording live.
Live trading is enabled only after a strategy survives OOS + walk-forward + paper, and account/PDT status is confirmed.
**Status:** Not started. LULD halt detection added to RiskGate (Batch 6). Remaining: IBKRBroker impl, nautilus_trader engine integration, real-time data, corporate-actions calendar, reconnect/re-arm, Terraform deploy, observability.

## Phase 2 (post-build)
New `ResearchDomain` impls (fundamental/technical, event-study validation mode) + new `MarketDataProvider`s
+ new tools, all reusing M3–M8 unchanged. The invariant holds across phases: LLM proposes, harness gates,
human approves, deterministic code executes inside guardrails.
