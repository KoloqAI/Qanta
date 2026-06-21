# 04 — Safety & Auth

## Execution guardrails (enforced in M7 Risk — non-overridable)
Every order, paper or live, passes through `RiskGate.check()` before leaving M6. No path bypasses it.
- Per-position stop-loss — mandatory; no position opens without one.
- Max position size (per symbol) and max gross exposure (portfolio) — hard caps.
- Daily-drawdown kill-switch — if daily realized+unrealized loss crosses the threshold, flatten all and halt until manual reset.
- Violations are rejected and logged, never silently clamped.
- Live deployment requires both a passing `ValidationReport` and an `Approval` row bound to the exact `strategy_version` and a `user_id`. Assert both before the runtime starts.
- PDT guard: `horizon_mode == intraday` and account equity < $25,000 → block live intraday with a clear error; offer swing mode.
- Fail closed: when unsure whether an action is safe, reject and log.

- Broker-resident protection: every live position opens as a native bracket/OCO so its stop rests at the broker and survives a Quanta/Gateway crash; our engine stop is a secondary overlay. A dead-man's-switch watchdog halts new entries + alerts on heartbeat loss (relies on broker-side stops, does not blind-liquidate). Trading halts disable entries while keeping stops. Full detail in doc 12.
- Portfolio scope: orders also pass a `PortfolioRiskGate` (aggregate per-symbol/sector exposure, gross cap, cash buffer) after the per-order gate; both must pass. See doc 12.

## Permission tiers (apply to the agent AND the assistant)
- `read` (query/scan/analyze/backtest/validate) — execute freely.
- `risk_reducing` (pause/flatten/halt) — assistant may execute; fails safe.
- `risk_increasing` (deploy-live/approve/raise-limit/place-order) — never executed by an LLM. The
  assistant stages the action and the user confirms through the proper gate; deterministic code executes.
- No LLM call anywhere in M6/M7. The assistant is a faster on-ramp to the gates, never a way around them.

## Assistant stage-and-confirm
A consequential request returns a staged action card (full parameters + the guardrails that will apply)
with explicit confirm/cancel. Confirmation creates the same `Approval`/audit record any other path would.
Every assistant action — read, executed, or staged — is written to the audit log.

## Auth & account (M0)
- Single-user by default; built multi-user-ready (every record scoped by `user_id`).
- Credentials: argon2-hashed password or passkey/WebAuthn. Server-side session via httpOnly, SameSite cookie; CSRF protection on mutating routes. Session expiry + refresh.
- Authorization: `current_user` dependency on every non-public route; all mutating/consequential endpoints require an authenticated user; approval and audit records reference that user.
- Secrets: broker credentials and LLM provider keys live in a vault (AWS Secrets Manager; local dev `.env`). Broker creds are injected ONLY into the execution service scope — never the research agent, never the client. LLM keys never reach the browser.
- Account screen (under Settings): manage credentials/sessions, connected broker & data accounts, and LLM provider keys.

## Audit & observability
Immutable `audit_log` for every signal, order, fill, rejection, approval, kill-switch event, assistant
action, and evolution change. Calibration data (confidence vs realized) captured for the Performance screen.
