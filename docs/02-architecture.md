# 02 — Architecture

## Principles
1. Stable interfaces, replaceable intelligence — modules talk through versioned contracts; LLM, data, broker swappable.
2. The LLM is boxed — research/authoring only; no path to execution; separate process; no broker creds.
3. Deterministic where money moves — execution + risk are plain, auditable, fully tested.
4. Modular monolith first, services-ready — clean module boundaries; any module extractable later.
5. Everything is a tool — capabilities are registered tools (permission-tiered), callable by agent or workflow.
6. Same artifact everywhere — identical containers local and cloud; config differs, not code.

## Stack (pin these versions)
- Python 3.12 · FastAPI 0.115+ · Pydantic v2 · SQLAlchemy 2 + Alembic · Arq + Redis 7 (async, lightweight).
- LLM gateway: LiteLLM (routes to Ollama local + Bedrock/Vertex/Azure + direct API). Agent orchestration: LangGraph.
- Data: OpenBB ODP + IBKR market data (or a dedicated vendor — Polygon/Databento) behind a `MarketDataProvider` interface; swap feeds without touching strategy/engine code.
- Engine: nautilus_trader — unified, deterministic, event-driven engine for BOTH backtest and live (research-to-live parity; collapses the old realism-check + execution into one engine, eliminating backtest-vs-live drift). Pre-2.0, so pin versions and track release notes. PyBroker (NumPy+Numba; walk-forward + bootstrap) is OPTIONAL, added only for fast vectorized parameter sweeps if nautilus's event-driven search is too slow for our volume. backtrader and free vectorbt are maintenance-only/stale in 2026 — do not use. All behind `Backtester`/`Broker` interfaces, so swapping is config, not a rewrite.
- Stores: Postgres 16 for app state + time-series (start here); add TimescaleDB only when bar/tick volume demands it. DuckDB/Parquet for local analytical replay. Redis for cache/bus. Avoid carrying a dual analytical store early.
- Broker: IBKR via nautilus_trader's stable Interactive Brokers adapter, behind our `Broker` interface (IBKR Pro recommended for SmartRouting/execution quality; Lite for $0-commission). Live runs through IB Gateway headless (IBeam, containerized). Paper trading supported. Alpaca remains a drop-in alternative behind the same interface if ever desired.
- Frontend: React 18 + TypeScript 5 + Vite · Tailwind + shadcn/ui · lightweight-charts (price) + Recharts (analytics) · TanStack Query.
- Auth: server-side sessions (httpOnly cookie) or OAuth/OIDC if hosted; argon2 password hashing or passkey/WebAuthn; secrets in AWS Secrets Manager (or local .env via dotenv for dev).
- Infra: Docker + docker-compose (local); Terraform + ECS/Fargate (AWS).

## Repository file tree (target)
```
quanta/
  docker-compose.yml
  pyproject.toml
  alembic/
  app/
    main.py                 # FastAPI app factory, router mounting
    config.py               # pydantic-settings; all env config
    deps.py                 # DI: db session, current_user, services
    api/                    # routers: auth, strategies, research, deployments,
                            #   portfolio, performance, evolution, assistant, settings, ws
    core/
      tools/                # tool registry + base Tool; permission tiers
      dsl/                  # strategy DSL: primitives, schema, parser/validator, interpreter
    modules/
      auth/                 # M0  users, sessions, authz
      data/                 # M1  MarketDataProvider impls, FeatureStore, point-in-time
      research/             # M2  agent (LangGraph), ResearchDomain, StrategyAuthor, LLMProvider via LiteLLM
      registry/             # M3  Strategy + versions + lifecycle
      backtest/             # M4  Backtester impls, cost model
      validation/           # M5  walk-forward, DSR, PBO, robustness, confidence, ledger, lockbox + tests
      execution/            # M6  deterministic ExecutionRuntime, Broker impls (holds broker creds)
      risk/                 # M7  pre-trade guardrails, kill-switch
      monitoring/           # M8  perf, decay, calibration, audit log
      news/                 # optional capability module (default off)
      evolution/            # scheduled loop: promote/retire, discover, propose; meta-lockbox
    models/                 # SQLAlchemy ORM
    schemas/                # Pydantic DTOs
    workers/                # Arq tasks (research runs, backtests, evolution)
  web/                      # React app (see doc 05 for screens)
  tests/                    # pytest; per-module + safety drills + harness verification suite
```

## Modules
| # | Module | Responsibility | Key interfaces |
|---|--------|----------------|----------------|
| M0 | Auth | users, sessions, authorization; subject of approvals/audit | `AuthService`, `current_user` dep |
| M1 | Data | ingest/normalize point-in-time, survivorship-free data; features | `MarketDataProvider`, `FeatureStore` |
| M2 | Research | LLM analyst; emits Strategy Specs + thesis; red-team; logs trials | `LLMProvider`, `ResearchDomain`, `StrategyAuthor` |
| M3 | Registry | versioned specs + lifecycle `draft→backtested→validated→approved→paper→live→retired` | `StrategyRegistry` |
| M4 | Backtest | run spec vs history with realistic costs | `Backtester` |
| M5 | Validation | gauntlet + confidence + ledger + lockbox + verification suite | `ValidationHarness` |
| M6 | Execution | deterministic runtime; broker orders; holds creds | `Broker`, `ExecutionRuntime` |
| M7 | Risk | non-overridable pre-trade guardrails + kill-switch | `RiskGate` |
| M8 | Monitoring | perf, decay, calibration, immutable audit | `MonitoringService`, `AuditLog` |
| — | Evolution | scheduled promote/retire/discover/propose | `EvolutionLoop` |
| — | News (optional) | sentiment features + veto; registers/deregisters its tools | `NewsProvider` |

| — | Portfolio | capital allocation across live strategies + portfolio-scope risk gate | `Allocator`, `PortfolioRiskGate` |
| — | Scheduling | market calendar, trading windows, EOD flatten, job cadence | `Scheduler`, `MarketCalendar` |
| — | Notifications | out-of-band alerts (email/Telegram/SMS) by event severity | `Notifier` |

(Portfolio, Scheduling, Notifications, plus broker-resident protective orders and corporate-action/halt
handling, are specified in doc 12. Data-model additions: `deployments.capital_budget`; configs
`portfolio.yaml`, `notifications.yaml`.)

## Key interface contracts (illustrative signatures)
```python
class MarketDataProvider(Protocol):
    def bars(self, symbol: str, start, end, tf: str, as_of: datetime) -> DataFrame: ...   # point-in-time
    def universe(self, as_of: datetime) -> list[str]: ...                                 # incl. delisted

class LLMProvider(Protocol):                      # implemented over LiteLLM; tier-routed
    def complete(self, messages, tools=None, tier: Literal["local","mid","frontier"]="mid") -> LLMResult: ...

class Backtester(Protocol):
    def run(self, spec: StrategySpec, window: DateWindow, costs: CostModel) -> BacktestResult: ...

class ValidationHarness(Protocol):
    def validate(self, spec: StrategySpec, n_eff: int) -> ValidationReport: ...  # walk-forward, DSR, PBO, robustness, peers

class RiskGate(Protocol):
    def check(self, order: Order, book: BookState) -> RiskDecision: ...  # reject+log on violation; never silently clamp

class Broker(Protocol):                            # IBKRBroker (via nautilus) | PaperBroker
    def submit(self, order: Order) -> OrderAck: ...
    def flatten_all(self) -> None: ...

class Tool(Protocol):
    name: str; permission: Literal["read","risk_reducing","risk_increasing"]; cost_tier: str
    def invoke(self, args: dict, ctx: ToolContext) -> ToolResult: ...
```

## Tool registry & permission tiers
Every capability is a registered `Tool` with a `permission` tier:
- `read` — query/scan/analyze/backtest/validate. Agent and assistant invoke freely.
- `risk_reducing` — pause/flatten/halt. Assistant may execute (fails safe).
- `risk_increasing` — deploy-live/approve/raise-limit/place-order. **Never invoked by the LLM.** Staged for human confirm; executed only by deterministic code after an `Approval`.
Optional modules register/deregister their tools (module off → tool absent → graceful degradation).
Workflows are declarative tool pipelines (same registry) used by the evolution loop and scheduled jobs.

## Data model (core entities)
`users` · `sessions` · `strategies` · `strategy_versions(rules jsonb, thesis, state)` ·
`research_runs(goal, trials_count)` · `trials(params, in_sample_sharpe)` ·
`backtest_runs(sharpe, max_dd, equity_curve)` · `validation_reports(deflated_sharpe, pbo, slope, peer_hit, passed, confidence_curve jsonb)` ·
`deployments(mode, status)` · `orders` · `fills` · `approvals(user_id, approved, reason)` ·
`audit_log(actor, action, subject, ts)` · `search_ledger(spec_hash, family, n_eff_contrib, model_version)`.
Relationships: strategy 1..* version; version 1..1 validation_report, 1..* backtest_run, 1..* deployment;
deployment 1..* order; order 1..* fill; research_run 1..* version, 1..* trial; user 1..* approval.

## Deployment & scaling
- Local: `docker compose up` → api, worker, web, postgres, redis, ollama.
- AWS: ALB → ECS/Fargate (api, web, workers) · RDS Postgres+Timescale · ElastiCache Redis · Secrets Manager · LLM via Ollama-on-EC2 or hosted. Terraform-provisioned.
- Stateless services; horizontal scale on the worker tier; execution module extractable to its own service (and its own secret scope) when isolation is wanted.
- Indicative cost: $0–100/mo local (free data + paper); ~$100–250/mo small AWS.
