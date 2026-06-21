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
  POST   /strategies/{id}/approve         # body: {approved, reason}; creates Approval (risk_increasing)
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
Settings
  GET/PUT /settings/connections /settings/models /settings/risk
          /settings/validation /settings/tools /settings/workflows
          /settings/account /settings/appearance   # appearance: {theme: system|light|dark}
WS
  /ws/jobs/{id}   /ws/monitor   /ws/assistant
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
validation_reports(id pk, strategy_version_id fk, deflated_sharpe float, pbo float,
                   deg_slope float, peer_hit float, n_eff int, passed bool,
                   confidence_curve jsonb, detail jsonb, created_at)
deployments(id pk, strategy_version_id fk, mode enum(paper,live), status, guardrails jsonb,
            capital float, started_at, ended_at)
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
```
Scope every user-owned row by `user_id` (single-user now, multi-user-ready).

## Tool catalog (registered tools; `permission` governs who/what may invoke)
| Tool | Permission | In → Out |
|------|------------|----------|
| `universe_scan` | read | filter spec → candidate tickers |
| `technical_analysis` | read | ticker, indicators → analysis (uses DSL features) |
| `characterize_ticker` | read | ticker → regime/behavior profile + stats |
| `news_search` | read | ticker/window → news items (only if news module enabled) |
| `author_strategy` | read | thesis + intent → DSL spec |
| `backtest` | read | spec, window → BacktestResult |
| `validate` | read | spec → ValidationReport (gauntlet; logs to ledger) |
| `peer_test` | read | spec, peers → peer-hit distribution |
| `query_book` | read | — → portfolio/positions/exposure |
| `query_performance` | read | filter → history, realized-vs-expected, calibration |
| `pause_deployment` `flatten_deployment` `halt_deployment` | risk_reducing | deployment_id → ack (assistant may execute; fail-safe) |
| `deploy_strategy` `approve_strategy` `promote_to_live` `set_guardrail` `place_order` | risk_increasing | … → STAGED only; executed by deterministic code after an Approval; never invoked by an LLM |

Workflows are declarative pipelines over these tools (e.g., evolution T2: `universe_scan → author_strategy → backtest → validate`), runnable on a schedule without an interactive agent.
