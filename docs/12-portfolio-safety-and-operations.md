# 12 — Portfolio, Broker-Side Safety & Operations

Closes the gaps for unattended real-money running. All deterministic; no LLM in any of it.

## 1. Capital allocation & portfolio risk (new module: Portfolio)
The per-strategy sizing and global guardrails don't decide how the account is split across live
strategies or control concentration that's only visible at the book level. Add a Portfolio module:
- **Allocator (deterministic):** each live deployment gets a `capital_budget` = a fraction of deployable
  equity, set in Deploy Config. Methods: `fixed_fraction` (default), `inverse_vol`, `confidence_weighted`
  (scaled by the deflated lower-bound C_lo). Sum of budgets ≤ deployable equity − `cash_buffer`.
- **PortfolioRiskGate (superset of the per-order RiskGate, equally non-overridable):** aggregate per-symbol
  exposure across ALL strategies (offsetting positions net), max gross portfolio exposure, sector/group
  concentration cap, max simultaneous strategies, and a correlation watch (rolling corr of strategy returns
  + position overlap). Orders breaching a portfolio cap are **rejected, not clamped**.
- **Order flow:** per-order RiskGate → PortfolioRiskGate → broker. Both must pass.
- v1 stays simple: per-symbol aggregate cap + sector cap + cash buffer + max-N-strategies; correlation-aware
  sizing is a later enhancement. Config in `config/portfolio.yaml`; `deployments.capital_budget` added.

## 2. Safety at the broker — protective orders + dead-man's switch (extends Risk + Execution)
Our stop is evaluated by our engine; if the engine or IB Gateway dies, positions must not be left naked.
- **Broker-resident protection:** every live position opens as a native bracket/OCO — entry + a stop (and
  optional take-profit) submitted so the stop **rests at IBKR** and survives a Quanta/Gateway crash. Our
  engine's stop is a secondary, possibly tighter overlay — never the only line of defense.
- **Heartbeat/watchdog:** the execution runtime emits a heartbeat; a separate watchdog monitors it. On
  heartbeat loss, DO NOT blind-liquidate (broker stops cover the downside) — instead halt new entries, fire
  a critical notification, and rely on broker-resident protection. Optional stricter mode: enable IBKR's
  auto-cancel/auto-liquidate-on-disconnect.
- **On reconnect/restart:** reconcile positions and orders with the broker and **re-arm any missing
  protective orders before resuming**; refuse to trade until reconciled.
- **Kill-switch:** flattens via the broker; if connectivity is down, broker-resident stops are the fallback.

## 3. Market calendar & scheduler (new module: Scheduling)
Use `exchange_calendars`/`pandas-market-calendars` for NYSE/NASDAQ holidays, half-days, and sessions.
- **Trading windows:** no actions on holidays; respect early closes; pre/post-market only if enabled.
- **EOD policy per deployment:** `intraday` auto-flattens N minutes before close (configurable buffer);
  `swing` holds overnight (subject to PDT). Ties to the PDT guard.
- **Scheduled jobs:** evolution T1/T2 cadence, data refresh, calibration resolution, nightly ledger tasks.
- Deterministic — no trading action fires outside a permitted window.

## 4. Notifications (new module: Notifications)
- **Channels:** email (SES), Telegram, optional SMS, routed by event → severity → channel.
- **Critical out-of-band events:** kill-switch fired, broker/data disconnect, large drawdown, strategy
  awaiting review, deploy/approval, guardrail trips, evolution Tier-3 proposal.
- Settings → Notifications: channels, per-severity routing, quiet hours. Every notification is also audited.

## 5. Corporate actions & trading halts (extends Data + Risk + Monitoring)
- **Backtest data:** split/dividend-adjusted point-in-time series + raw, plus a corporate-actions calendar;
  adjustments must not introduce lookahead.
- **Live:** subscribe to LULD halts and corporate-action notices. On a halt for a held symbol — disable
  entries, hold, keep protective stops, surface a degraded state. On an overnight split/symbol change —
  reconcile quantity/symbol at next open before the strategy acts; if the action invalidates a strategy's
  levels or regime, flag for review and pause it.

## 6. Historical data sourcing (decision — M2 prerequisite)
Validation rigor depends on survivorship-free, point-in-time data including delisted names; free
aggregators won't reliably deliver this.
- **Decision:** source survivorship-free history from a vendor — Norgate Data (inexpensive survivorship-free
  EOD, popular for backtesting) or Polygon.io / Databento (intraday + delisted). Live data from IBKR/Polygon.
  All behind `MarketDataProvider`.
- **M2 prerequisite gate:** confirm the chosen source actually delivers survivorship-free PIT incl. delisted
  BEFORE building the harness (M3). Do not build validation on data that can't support it.

### Reconstitution calendar (required new data feed)
The `forced_flow` archetype family (doc 13) requires an **index reconstitution calendar** with three dates
and a direction per name: `preliminary_list_date`, `final_list_date`, `effective_date`, `action` (add/delete).
This is available via `MarketDataProvider.reconstitution_events(index, as_of)`, point-in-time: events are
only revealed once `as_of >= final_list_date` to prevent lookahead (the announcement-to-effective drift is
the signal; backfilling membership before the list was public manufactures a fake edge).

**Polygon's standard OHLCV does not include index membership changes.** A dedicated feed is required:
FTSE Russell published reconstitution schedules/lists, or a vendor carrying index membership changes
(ICE, Bloomberg). Wire as a sibling of the corporate-actions calendar — scheduled, dated, point-in-time.
`SampleDataProvider` includes a deterministic synthetic reconstitution calendar for testing (Russell 2000,
two years of adds/deletes including delisted names for survivorship-free testing).

### Earnings calendar (required new data feed)
The `behavioral_drift` archetype family (doc 13) requires an **earnings announcement calendar** per ticker,
point-in-time, with a **BMO/AMC** session flag (before market open vs after market close) that determines
which bar shows the reaction.  Available via `MarketDataProvider.earnings_events(symbol, start, end, as_of)`;
announcements are only revealed once `announce_date <= as_of` to prevent lookahead.

**V1 surprise proxy:** instead of analyst-estimate SUE data, measure the earnings reaction directly from
price/volume on the announcement bar (zscore of the close-to-close return + volume spike ratio).
**Upgrade path (Phase 2):** real SUE from an estimates vendor → cleaner surprise signal.
**V1 neglect proxy:** low `avg_volume(20)` as a proxy for "few analysts, low institutional ownership."
**Upgrade path (Phase 2):** analyst-coverage count + institutional-ownership % from a reference vendor.

`SampleDataProvider` includes a deterministic synthetic quarterly earnings calendar for all sample
universe tickers + delisted names (2022-2025).  `PolygonDataProvider` requires a financials/reference
subscription or a dedicated earnings-date vendor — the standard OHLCV plan does not include earnings dates.

## 7. Deferred (acknowledged, not built now)
- **Tax/accounting export:** realized P&L, wash-sale flags, 1099 reconciliation, CSV/JSON export — post-live.
- **LLM/data $-cost governor:** a monthly spend cap + alert in Settings (distinct from the statistical
  search-budget ledger). Simple v1; expand only if spend grows.

---
These close the open gaps. From here, remaining unknowns are milestone-local — resolve them at each
acceptance gate during the build, not with more upfront design.
