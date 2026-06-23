# TECH-STACK

Single source of truth for technology choices. Pin exact versions at build time; verify the latest stable
then. nautilus_trader especially is pre-2.0 — pin it and track release notes. Rationale in docs 02, 11, 12.

## Backend (Python)
| Area | Choice | Notes |
|------|--------|-------|
| Language | Python 3.12 | |
| Web framework | FastAPI 0.115+ + Uvicorn | async API |
| Validation/DTOs | Pydantic v2 + pydantic-settings | typed boundaries; env config |
| ORM / migrations | SQLAlchemy 2.x + Alembic | migrations only — never hand-edit schema |
| Task queue | Arq + Redis 7 | async, lightweight (chosen over Celery) |
| Trading engine | **nautilus_trader** | unified backtest + live, research-to-live parity, deterministic; pre-2.0 → pin |
| Sweep engine (optional) | PyBroker | add only if vectorized sweeps needed; also used as an independent validation cross-check |
| Broker | **IBKR** via nautilus IBKR adapter | Pro (SmartRouting) or Lite ($0 comm.); behind `Broker` interface |
| Broker connectivity | IB Gateway + IBeam | headless auth/run, containerized |
| Historical data | Norgate / Polygon.io / Databento | survivorship-free, point-in-time incl. delisted (M2 prerequisite) |
| Live/aux data | OpenBB **ODP** (open-source, self-hosted, free; AGPL — fine for personal use, revisit if multi-tenant SaaS) + IBKR/Polygon | behind `MarketDataProvider`. Use the open-source Open Data Platform, NOT OpenBB Workspace (the cloud UI/Copilot product — not needed). ODP doesn't serve data; you supply provider API keys. |
| Validation math | own impl on numpy/scipy/pandas | DSR/PBO/walk-forward; mlfinpy/PyBroker for triangulation |
| Market calendar | exchange_calendars / pandas-market-calendars | holidays, half-days, sessions, EOD flatten |
| LLM gateway | LiteLLM | routes to local + hosted; tiered; with fallbacks; never in execution path |
| Local models | Ollama | cheap/grunt tier; best-effort with hosted failover |
| Hosted models | Bedrock / Vertex / Azure / direct API | mid/frontier tiers |
| Agent orchestration | LangGraph (or thin custom loop) | young — pin, keep debuggable |
| Auth | argon2-cffi or passkey/WebAuthn (py_webauthn) | server-side sessions, CSRF, secure cookies |
| Secrets | AWS Secrets Manager (boto3); local `.env` via python-dotenv | broker/LLM keys scoped away from client + agent |
| Notifications | AWS SES (email), python-telegram-bot, optional Twilio (SMS) | out-of-band alerts by severity |

## Data stores
| Store | Choice | Notes |
|-------|--------|-------|
| App + time-series | Postgres 16 | start here; add TimescaleDB only when bar/tick volume demands |
| Cache / bus / sessions | Redis 7 | |
| Analytical replay | DuckDB / Parquet | local backtest data reads only — not the system of record |

## Frontend
| Area | Choice | Notes |
|------|--------|-------|
| Framework | React 18 + TypeScript 5 + Vite | |
| Styling | Tailwind CSS + shadcn/ui (Radix) | |
| Server state | TanStack Query | |
| Price charts | lightweight-charts | |
| Analytics charts | Recharts | |
| Fonts | Space Grotesk / Inter / JetBrains Mono | display / body / mono numerals |
| Theming | CSS variables + `data-theme` (system/light/dark) | persisted user preference; see docs/10 |

## Infra / Ops
| Area | Choice | Notes |
|------|--------|-------|
| Local | Docker + docker-compose | api, web, worker, postgres, redis, ollama, ib-gateway/ibeam |
| Cloud | Terraform → AWS ECS/Fargate | ALB, RDS Postgres, ElastiCache Redis, Secrets Manager, SES |
| CI | GitHub Actions + pytest | hash-pinned deps; verify nautilus signed wheels/SBOM |
| Observability | structured logs + metrics + alerts | fills, rejections, guardrail trips, kill-switch, data gaps |

## Hard rules that constrain the stack
- No LLM library or call anywhere in the execution (M6) or risk (M7) path.
- Everything swappable sits behind an interface: `MarketDataProvider`, `LLMProvider`, `Broker`,
  `Backtester`, `ResearchDomain`, `Tool`. New capability = new impl, not a core edit.
- Same container images locally and in AWS; behavior differs by config, never by environment branch.