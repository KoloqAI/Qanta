# 11 — Production Readiness & Scaling

## What "production-ready" means here
This is a single-operator system that trades real money — so "production-ready" means reliability,
determinism, safety, reproducibility, and observability, NOT high web concurrency. The scale axes that
matter are: (1) market-data volume, (2) backtest/search throughput, (3) live-execution reliability.
Don't gold-plate for multi-tenant web traffic we don't have; do harden the money-path.

## Per-layer status (all choices vetted, mid-2026)
| Layer | Choice | Status |
|-------|--------|--------|
| API/runtime | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic | Production-grade, standard. |
| Workers | Arq + Redis | Production-grade, async, right-sized (lighter than Celery). |
| Engine (backtest+live) | nautilus_trader | Production-grade architecture (deterministic, Rust core, signed/SLSA releases, bi-weekly). Pre-2.0 → pin versions, track release notes. |
| Sweeps (optional) | PyBroker | Maintained; add only if sweep throughput demands. Keep behind `Backtester`. |
| Broker | IBKR (Pro rec.) via nautilus stable adapter | Production-grade; IB Gateway headless via IBeam. Alpaca swappable behind `Broker`. |
| Data | OpenBB ODP + IBKR/vendor | Behind `MarketDataProvider`; upgrade to Polygon/Databento for intraday robustness. |
| LLM | LiteLLM → Ollama + hosted | Production-grade gateway. Route with FALLBACKS; treat local Ollama as best-effort with hosted failover. Never in the execution path. |
| Agent orchestration | LangGraph (or thin custom loop) | Young/fast-moving; pin, keep the loop debuggable. |
| Stores | Postgres 16 (+ Timescale later) + Redis | Production-grade, scalable; DuckDB/Parquet for analytical replay only. |
| Frontend | React + TS + Vite + Tailwind + shadcn | Production-grade. |
| Auth | argon2/passkey + server-side sessions + Secrets Manager | Production-grade; sessions in Redis/DB for horizontal scale. |
| Infra | Docker + Terraform + ECS/Fargate | Production-grade; stateless services scale horizontally. |

## Scaling the three axes
- **Data volume:** Postgres now; partition/Timescale when bar/tick volume warrants; Parquet/DuckDB for replay. Cache hot reads in Redis.
- **Search throughput:** parallel Arq workers; nautilus for realism; add PyBroker vectorized sweeps if needed. The search-budget ledger caps volume by design (and keeps deflation honest).
- **Execution reliability:** one deterministic engine (nautilus) for backtest+live parity; our RiskGate in front; idempotent order submission; broker-state reconciliation on (re)connect; the daily kill-switch; full audit log.

## Production hardening checklist (gate for M9, before any live capital)
- Idempotency keys on every order; reconcile open orders/positions with the broker on startup and reconnect.
- Connectivity resilience: IB Gateway/IBeam auto-reauth + reconnect; on data-feed loss, degrade safe (pause new entries, keep stops) and surface the degraded state in the top bar.
- Observability: structured logs, metrics, and alerts for fills, rejections, guardrail trips, kill-switch, data gaps, and agent/evolution actions.
- Reproducibility: pin all dependency versions (nautilus especially); record model + data + code provenance per run so any result re-runs identically.
- Data safety: automated Postgres backups + tested restore; migrations via Alembic only.
- Secrets: vault-stored, rotated; broker creds scoped to the execution service only; never logged, never in client bundles.
- Supply chain: pinned, hash-checked deps; verify nautilus's signed wheels/SBOM.
- Re-run the M5 safety drills (stop-loss, caps, kill-switch, PDT block) in the deploy target; confirm identical behavior local vs AWS.
- Live enablement only after a strategy clears OOS + walk-forward + paper, and account/PDT status is confirmed.

## Decision record — broker & engine (mid-2026)
Chose **IBKR + nautilus_trader** over Alpaca + a self-built engine because nautilus's IBKR adapter is
stable (Alpaca's is an unbuilt RFC), giving one deterministic engine with research-to-live parity — the
strongest production-ready, low-drift posture. IBKR Lite matches Alpaca's $0 commissions; Pro adds
SmartRouting. Tradeoff accepted: live runs through a headless IB Gateway (IBeam). Everything stays behind
`Broker`/`Backtester` interfaces, so reversing to Alpaca or adopting nautilus's Alpaca adapter later is a swap.
