# Quanta — Personal AI Trading Research & Execution Platform

An LLM research analyst **proposes** trading strategies, a rigorous validation harness **proves or kills**
them, you **approve**, and a deterministic engine **executes** inside hard risk guardrails.
Phase 1: day / short-term US equities.

> **Prime directive:** No LLM output ever places, sizes, or cancels a live order. LLM proposes;
> human approves; deterministic code executes inside guardrails.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker Desktop | 4.x+ | Runs all services; must have Compose v2 |
| Git | any | |
| Python | 3.12+ | Only needed for local dev outside Docker |
| Node.js | 20+ | Only needed for local frontend dev outside Docker |

---

## External Services & Subscriptions

The table below lists every external dependency. Mark what you need for your phase of build.

### Required (core stack — always needed)

| Service | Purpose | How to get it |
|---------|---------|----------------|
| **IBKR account** | Paper + live order execution | [interactivebrokers.com](https://www.interactivebrokers.com) — Individual or Pro account. Enable API access in Account Settings. |
| **IB Gateway / TWS** | Local broker connection | Download from IBKR. Run on the host; the app connects via TCP (`IBKR_HOST`, `IBKR_PORT`). Paper trading uses port `4002`; live uses `4001`. |

### LLM Provider — choose at least one

| Provider | `.env` key | Notes |
|----------|-----------|-------|
| **Ollama (local)** | `OLLAMA_BASE_URL` | Free. Bundled in `docker-compose.yml`. Runs grunt-tier models locally (Llama 3, Mistral, etc.). No API key needed. |
| **OpenAI** | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) — GPT-4o for mid tier. |
| **Anthropic** | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) — Claude Sonnet/Opus for frontier tier. |
| **AWS Bedrock** | `AWS_BEDROCK_REGION` + AWS credentials | [aws.amazon.com/bedrock](https://aws.amazon.com/bedrock) — Titan / Claude / Llama via Bedrock. Requires `~/.aws/credentials` or IAM role. |

At least one hosted provider is recommended alongside Ollama. LiteLLM routes by task tier with fallbacks.

### Market Data — choose based on your needs

| Provider | Purpose | Where to get it |
|----------|---------|-----------------|
| **OpenBB ODP** | Live + historical equity data | [openbb.co](https://openbb.co) — free tier available. Set `OPENBB_API_KEY` in `.env`. |
| **Polygon.io** | Historical + live US equities | [polygon.io](https://polygon.io) — Starter plan minimum for historical. Set `POLYGON_API_KEY` in `.env`. |
| **Norgate Data** | Survivorship-free historical data | [norgatedata.com](https://norgatedata.com) — subscription required; point-in-time including delisted tickers. Strongly recommended for backtesting. |
| **Databento** | Institutional-grade tick/bar data | [databento.com](https://databento.com) — pay-per-query; best for high-quality backtests. Set `DATABENTO_API_KEY` in `.env`. |
| **IBKR data feed** | Live quotes via IB Gateway | Included with IBKR account. No separate key needed. |

### Notifications — optional, all can be left blank

| Provider | Purpose | Where to get it |
|----------|---------|-----------------|
| **AWS SES** | Email alerts (fills, kill-switch events) | [aws.amazon.com/ses](https://aws.amazon.com/ses) — requires verified sender domain. Set `SES_REGION` + `SES_FROM_EMAIL`. |
| **Telegram Bot** | Real-time trade notifications | [t.me/BotFather](https://t.me/BotFather) — create a bot, get `TELEGRAM_BOT_TOKEN` and your `TELEGRAM_CHAT_ID`. |

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in the values relevant to your setup:

```bash
cp .env.example .env
```

### `.env` reference

```dotenv
# ── Database (managed by Docker; change only if running Postgres externally) ─
DATABASE_URL=postgresql+asyncpg://quanta:quanta@localhost:5432/quanta
DATABASE_URL_SYNC=postgresql://quanta:quanta@localhost:5432/quanta

# ── Redis (managed by Docker; change only if running Redis externally) ────────
REDIS_URL=redis://localhost:6379/0

# ── Auth ──────────────────────────────────────────────────────────────────────
# REQUIRED: generate a strong random secret (e.g. `openssl rand -hex 32`)
SECRET_KEY=change-me-to-a-random-secret
SESSION_EXPIRE_MINUTES=1440          # 24 hours; adjust as needed

# ── LLM (at least one provider required) ─────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434   # bundled in Docker; keep as-is
LITELLM_API_KEY=                         # optional: LiteLLM proxy key if self-hosting proxy
OPENAI_API_KEY=                          # sk-...
ANTHROPIC_API_KEY=                       # sk-ant-...
GEMINI_API_KEY=                          # Google AI Studio key (gemini/* models)
AWS_BEDROCK_REGION=                      # e.g. us-east-1

# ── Broker (execution scope only — never exposed to the agent) ────────────────
# IB Gateway paper trading default: host=127.0.0.1, port=4002, client_id=1
# IB Gateway live trading:          port=4001
# TWS paper:                        port=7497
# TWS live:                         port=7496
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=1

# ── Market data (leave blank if not subscribed) ───────────────────────────────
OPENBB_API_KEY=
POLYGON_API_KEY=
DATABENTO_API_KEY=

# ── Notifications (all optional — leave blank to disable) ─────────────────────
SES_REGION=                  # e.g. us-east-1
SES_FROM_EMAIL=              # e.g. alerts@yourdomain.com
TELEGRAM_BOT_TOKEN=          # from BotFather
TELEGRAM_CHAT_ID=            # your personal or group chat ID

# ── Environment ───────────────────────────────────────────────────────────────
ENVIRONMENT=development
DEBUG=true
```

> `SECRET_KEY` **must** be changed before first run. Generate one:
> ```bash
> openssl rand -hex 32
> ```

---

## Build & Run

All operations go through `run.sh`. Make it executable once:

```bash
chmod +x run.sh
```

### First-time setup

```bash
./run.sh -f
```

This drops any existing containers/images/volumes and rebuilds everything from scratch. On first run
it pulls all base images and installs dependencies — expect 5–10 minutes.

Once up:
- **API** → [http://localhost:8000](http://localhost:8000)
- **UI** → [http://localhost:5173](http://localhost:5173)
- **API docs** → [http://localhost:8000/docs](http://localhost:8000/docs)

### All available commands

| Command | What it does |
|---------|-------------|
| `./run.sh -f` | **Fresh build** — drop all containers, images, volumes; rebuild from scratch |
| `./run.sh -ui` | **Rebuild frontend** — stop `web`, purge its image, rebuild with `--no-cache` |
| `./run.sh -bk` | **Rebuild backend** — stop `api` + `worker`, purge their images, rebuild with `--no-cache` |
| `./run.sh -up` | **Start** — bring all services up (no rebuild) |
| `./run.sh -down` | **Stop** — stop and remove containers; volumes are preserved |
| `./run.sh -logs` | **Logs** — stream logs for all services (`Ctrl-C` to stop) |
| `./run.sh -ps` | **Status** — show running container status |
| `./run.sh -db` | **DB shell** — open `psql` inside the Postgres container |
| `./run.sh -sh` | **API shell** — open `bash` inside the `api` container |
| `./run.sh -mig` | **Migrate** — run `alembic upgrade head` inside `api` |
| `./run.sh -test` | **Test** — run `pytest tests/ -v --tb=short` inside `api` |

### Database migrations

Migrations run automatically on `./run.sh -f`. For subsequent schema changes:

```bash
# Generate a new migration after editing models
./run.sh -sh
# inside the container:
alembic revision --autogenerate -m "describe the change"
exit

# Apply the migration
./run.sh -mig
```

---

## Architecture overview

```
LLM analyst (M2)  →  Validation harness (M3)  →  Human approval  →  Execution engine (M6)
                                                                          ↓
                                                              Risk gate M7 (always, no bypass)
```

- **M1** Market data — OpenBB ODP + IBKR feeds, behind `MarketDataProvider`
- **M2** Research — LangGraph agent, LiteLLM, proposes strategies as DSL
- **M3** Validation — walk-forward, DSR, PBO, confidence harness
- **M4** Backtest — nautilus_trader unified engine (backtest = live parity)
- **M5** Approvals — human gate; every approval is audit-logged
- **M6** Execution — deterministic, no LLM; nautilus_trader live
- **M7** Risk gate — stop-loss, position caps, daily drawdown kill-switch

Build strictly in the order defined in `docs/06-build-sequence.md`.

---

## Reference docs

| Doc | Purpose |
|-----|---------|
| `TECH-STACK.md` | Every technology choice with pinned versions |
| `STRUCTURE.md` | Authoritative target repository layout |
| `docs/01-product-and-scope.md` | Vision, scope, functional requirements |
| `docs/02-architecture.md` | Principles, stack, modules, contracts |
| `docs/03-engine-and-validation.md` | DSL, backtest, harness, confidence, evolution |
| `docs/04-safety-and-auth.md` | Guardrails, permission tiers, stage-and-confirm, auth |
| `docs/05-ux-flows-and-screens.md` | Flows, screen map, per-screen specs |
| `docs/06-build-sequence.md` | Phased milestones with acceptance gates |
| `docs/07-dsl-reference.md` | Full DSL primitive catalog, schema, interpreter contract |
| `docs/08-validation-internals.md` | Walk-forward, DSR, PBO, confidence, ledger |
| `docs/09-api-data-and-tools.md` | REST/WS surface, data model, tool catalog |
| `docs/10-theming-and-ui.md` | Theming, design tokens, UI states |
| `docs/11-production-and-scaling.md` | Production readiness, hardening checklist |
| `docs/12-portfolio-safety-and-operations.md` | Capital allocation, protective orders, market calendar |

## Design

`design/quanta-hifi-themed.html` — both hero screens with a live System / Light / Dark theme toggle.
Open in a browser (fonts load from Google Fonts).
