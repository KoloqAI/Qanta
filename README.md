# Quanta — Personal AI Trading Research & Execution Platform

A single-user platform where an LLM research analyst **proposes** trading strategies, a rigorous
validation harness **proves or kills** them, you **approve**, and a deterministic engine **executes**
inside hard risk guardrails. Phase 1: day / short-term US equities. Modular so fundamental/technical
long-term research bolts on later without a rewrite.

## The one rule that overrides everything
**No LLM output ever places, sizes, or cancels a live order.** LLM proposes/analyzes; a human approves;
deterministic code executes inside guardrails. Enforced in `.cursor/rules/02-trading-safety.mdc`.

## How to build with Cursor (read first)
Engineered for build in **small, verifiable increments** — not one mega-prompt. Open this folder as a
Cursor project (`.cursor/rules/*` load automatically). Build strictly in the order of
`docs/06-build-sequence.md`; each milestone has an **acceptance gate** — never advance past a red gate.
The safety-critical milestones (M3 validation, M5 execution+guardrails) must pass their test drills first.

## Quick reference
- `TECH-STACK.md` — every technology choice with pinned versions and rationale (single source of truth).
- `STRUCTURE.md` — the authoritative target repository layout + module dependency rules.

## Docs
| Doc | Purpose |
|-----|---------|
| `docs/01-product-and-scope.md` | Vision, users, scope, functional reqs, non-goals, success criteria |
| `docs/02-architecture.md` | Principles, stack+versions, file tree, modules, contracts, deployment |
| `docs/03-engine-and-validation.md` | Engine overview: DSL, backtest, harness, confidence, evolution (summary) |
| `docs/04-safety-and-auth.md` | Execution guardrails, permission tiers, stage-and-confirm, auth & secrets |
| `docs/05-ux-flows-and-screens.md` | Flows, screen map, per-screen specs |
| `docs/06-build-sequence.md` | Phased milestones with acceptance gates — the build spine |
| `docs/07-dsl-reference.md` | **Deep:** full DSL primitive catalog, schema, validation rules, interpreter contract |
| `docs/08-validation-internals.md` | **Deep:** walk-forward, DSR, PBO, confidence, ledger, verification suite (pseudocode) |
| `docs/09-api-data-and-tools.md` | Concrete REST/WS surface, column-level data model, tool catalog |
| `docs/10-theming-and-ui.md` | Theming mechanism, design tokens, signature component, UI states |
| `docs/11-production-and-scaling.md` | Production-readiness bar, per-layer status, scale axes, M9 hardening checklist, broker/engine decision record |
| `docs/12-portfolio-safety-and-operations.md` | Capital allocation + portfolio risk gate, broker-resident protective orders + dead-man's switch, market calendar/scheduler, notifications, corporate actions/halts, data-source decision |

## Design (visual source of truth)
`design/quanta-hifi-themed.html` — both hero screens with a live System/Light/Dark theme toggle.
`design/quanta-hifi-light.html` and `design/quanta-hifi-dark.html` — the two static variants.
Open in a browser (fonts load from Google Fonts). Tokens are documented in `docs/10`.

## Defaults (config, not code)
Broker: IBKR via nautilus_trader's stable IBKR adapter (Pro recommended; Lite for $0-commission), behind a `Broker` interface (Alpaca swappable). LLM: LiteLLM over local (Ollama) + Bedrock/Vertex/Azure + direct API, routed
by task tier; never in the execution path. Engine: nautilus_trader (unified backtest+live parity); PyBroker optional for fast sweeps. Data: OpenBB ODP + IBKR/vendor feeds. Store: Postgres 16 first (+ Timescale when volume needs it).
Cloud: AWS ECS/Fargate. News module: optional, default off. Theme: system default.
