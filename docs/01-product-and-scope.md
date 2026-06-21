# 01 — Product & Scope

## Vision
Pair a PhD-level AI research analyst with a skeptical validation engine and a deterministic,
safety-bounded executor. The analyst forms hypotheses and writes the test; the harness refuses to be
fooled by overfitting; the human makes the final call; the executor trades without discretion inside
hard limits. The durable asset is the ability to tell a real edge from a lucky-looking one.

## User
A single sophisticated operator trading a personal account. Designs imply one expert user, but the
system is stateless and modular so it could scale to multi-user without a rewrite.

## Scope — Phase 1
- Horizon: intraday through short-term holds of a few days.
- Instruments: US equities and equity ETFs. Options/crypto are post-Phase-1.
- Strategy families: structural/technical (range mean-reversion, RSI/indicator-directional, momentum,
  volatility). True fundamental/catalyst (event-study) is a later capability.
- PDT flag: live intraday in a margin account needs >= $25,000 equity. Below that, default to swing
  mode. Configurable: `trading.horizon_mode`.

## Functional requirements
1. **Auth & account** — login, secure session, account/profile; manage connected broker/data accounts
   and LLM provider keys; the authenticated identity is the subject of every approval and audit record.
2. **AI research analyst** — conversational + structured research; emits Strategy Specs (DSL rules +
   required economic thesis); runs a red-team critique; logs every variant tried (feeds validation N).
   Never issues/sizes/cancels live orders.
3. **Strategy authoring & backtest** — translate NL into a parameterized, versioned DSL spec; backtest
   on point-in-time, survivorship-free data with realistic costs.
4. **Validation harness** — purged walk-forward, DSR, PBO, robustness, peer test; pre-registered
   thresholds; lockbox; ships a known-truth verification suite. (doc 03)
5. **Confidence metric** — deflated, OOS, conditional probability of a defined outcome; gated, never LLM-authored. (doc 03)
6. **Human review & approval** — evidence vs counter-evidence; explicit approve/reject; approval is the
   only path to deployment.
7. **Paper trading** — required stage before live; live-vs-backtest divergence blocks promotion.
8. **Live execution** — deterministic; non-overridable guardrails (stop-loss, position/exposure caps,
   daily kill-switch). (doc 04)
9. **Assistant** — grounded NL interface over the whole app; read + risk-reducing actions execute,
   risk-increasing actions stage-and-confirm. (doc 04)
10. **Tools & workflows** — every capability is a registered tool, callable by the agent or by a
    declarative workflow. (doc 02)
11. **Evolution loop** — scheduled self-improvement: promote/retire, discover, propose capabilities;
    search-budget ledger + meta-lockbox keep it honest. (doc 03)
12. **Monitoring, performance & audit** — live oversight + intervention; portfolio overview; historical
    track record + confidence calibration; immutable audit log.

## Non-goals (Phase 1)
Multi-tenant SaaS; autonomous human-out-of-the-loop trading; sub-second HFT; options/futures/crypto;
third-party financial advice.

## Success criteria
1. Harness passes a seeded known-good strategy and fails a seeded known-overfit one.
2. Full paper loop works end to end: propose → validate → review → approve → paper → monitor.
3. Nothing reaches live without passing the harness AND an explicit human approval bound to a user.
4. Guardrail drills fire: stop-loss, position cap, daily kill-switch.
5. Runs identically via `docker compose up` locally and on AWS.
6. Adding a research domain requires no change to execution, risk, or auth modules.
