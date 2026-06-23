# STRUCTURE

Authoritative target repository layout (supersedes the inline tree in docs/02; includes the Portfolio,
Scheduling, and Notifications modules added in doc 12). Build the file tree to match this; when a path is
ambiguous, this file wins.

```
quanta/
├── README.md
├── TECH-STACK.md
├── STRUCTURE.md
├── docker-compose.yml              # api, web, worker, postgres, redis, ollama, ib-gateway/ibeam
├── pyproject.toml                  # pinned deps
├── .cursor/rules/                  # always-on agent rules (00–04)
├── docs/                           # 01–13 specification
├── design/                         # hi-fi mockups (visual source of truth)
├── config/
│   ├── guardrails.yaml             # global risk limits (per-trade stop, caps, daily kill-switch)
│   ├── validation.yaml             # pre-registered thresholds (DSR/PBO/slope/min-trades/peer)
│   ├── portfolio.yaml              # allocation method, per-symbol/sector caps, cash buffer, max strategies
│   ├── notifications.yaml          # channels + event→severity routing + quiet hours
│   ├── models.yaml                 # LiteLLM tier routing + fallbacks
│   └── library/                    # seed strategy archetypes (doc 13): one YAML per archetype
├── alembic/                        # migrations
├── app/
│   ├── main.py                     # FastAPI app factory, router mounting
│   ├── config.py                   # pydantic-settings; all env config
│   ├── deps.py                     # DI: db session, current_user, services
│   ├── api/                        # routers (thin)
│   │   ├── auth.py  strategies.py  research.py  deployments.py
│   │   ├── portfolio.py  performance.py  monitor.py  evolution.py
│   │   ├── assistant.py  settings.py  ws.py
│   ├── core/
│   │   ├── tools/                  # tool registry + base Tool + permission tiers
│   │   └── dsl/                    # primitives, schema, parser/type-checker, interpreter
│   ├── modules/
│   │   ├── auth/                   # M0  users, sessions, authz
│   │   ├── data/                   # M1  MarketDataProvider impls, FeatureStore, corp-actions, halts (HaltDetectorImpl)
│   │   ├── research/               # M2  LangGraph agent, ResearchDomain, StrategyAuthor, LLMProvider (LiteLLM)
│   │   ├── registry/               # M3  Strategy + versions + lifecycle + library_archetypes (doc 13)
│   │   ├── backtest/               # M4  Backtester (nautilus), cost model, (optional PyBroker)
│   │   ├── validation/             # M5  walk-forward, DSR, PBO, robustness, confidence, ledger, lockbox, verification suite
│   │   ├── execution/              # M6  ExecutionRuntime, Broker impls (IBKR/Paper), broker-resident brackets, heartbeat watchdog, DeploymentGate
│   │   ├── risk/                   # M7  RiskGate (per-order) + kill-switch
│   │   ├── portfolio/              # Allocator + PortfolioRiskGate (aggregate caps)
│   │   ├── scheduling/             # Scheduler + MarketCalendar (windows, EOD flatten via EODFlattenJob, job cadence)
│   │   ├── notifications/          # Notifier (email/Telegram/SMS) + watchdog/dead-man's-switch
│   │   ├── monitoring/             # M8  perf, decay, calibration, audit log
│   │   ├── evolution/              # scheduled promote/retire/discover/propose; meta-lockbox; seeded wide exploration (doc 13)
│   │   └── news/                   # optional capability module (default off)
│   ├── models/                     # SQLAlchemy ORM (see docs/09 data model)
│   ├── schemas/                    # Pydantic DTOs
│   └── workers/                    # Arq tasks (research runs, backtests, evolution, scheduled jobs)
├── web/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx  App.tsx  router.tsx
│       ├── theme/                  # CSS-var tokens, data-theme controller (system/light/dark)
│       ├── lib/                    # api client (TanStack Query), ws client, formatters
│       ├── components/             # shadcn/ui + app components (confidence-interval bar, stat card, status bar, staged-action card)
│       ├── hooks/
│       └── pages/                  # Login, Portfolio, Assistant, StrategyDetail, ReviewQueue,
│                                   #   Monitor, Performance, Registry (Instantiated + Library tabs),
│                                   #   BacktestSandbox, Evolution, Settings (+ DeployConfig modal)
├── ops/
│   └── ibeam/                      # IB Gateway headless auth config
├── terraform/                      # ECS/Fargate, RDS, ElastiCache, Secrets Manager, SES, ALB
└── tests/
    ├── unit/                       # per-module
    ├── safety/                     # M5 drills: stop-loss, caps, portfolio cap, broker-stop-survives-kill, EOD flatten, kill-switch, PDT
    ├── validation_suite/           # M3 verification suite (PBO≈0.5 on noise, DSR monotonic, skew penalty, triangulation, known-good/known-overfit)
    └── e2e/                        # full paper loop (propose→validate→approve→paper→monitor)
```

## Module dependency rules (enforced)
- `research` may call `data`, `registry`, `backtest`, `validation` interfaces — never `execution`, `risk`, or the broker.
- Order flow: `execution` → `risk.RiskGate` → `portfolio.PortfolioRiskGate` → broker. Both gates must pass.
- Optional modules (`news`) register/deregister their tools; the app runs fully with them off.
- Every module exposes a thin public `service.py`; never import another module's internals directly.