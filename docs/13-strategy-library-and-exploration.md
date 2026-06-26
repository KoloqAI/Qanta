# 13 — Strategy Library, Exploration & Manual Backtest

Closes three gaps: (1) the seed knowledge that tells the app what to look for, (2) a UI to browse the
universe of strategy archetypes/themes, (3) a hands-on way to backtest a strategy on a ticker + date range.

## Design principle (read first)
We seed a WIDE catalog of archetypes and let the agent explore aggressively from day one — but aggression
is in *hypothesis generation only*. Every trial (archetype × ticker × param set) is logged to the
search-budget ledger (doc 08 §6); effective-N rises with exploration; DSR/PBO thresholds deflate harder
automatically. Nothing reaches paper or live without the full gauntlet (doc 08) AND human approval. A wider
catalog therefore *raises* the bar, never lowers it. The per-period search budget caps how aggressive a
cycle is — set it high, but the ledger keeps deflation honest. Archetypes never auto-deploy.

## 1. Strategy Library (the seed knowledge)
A curated, versioned catalog of strategy archetypes, each a DSL template (doc 07) plus a scan playbook.
Seeds live as YAML in `config/library/*.yaml`, loaded in-memory on startup (DB-backed table planned); editable;
the evolution loop appends *proven, human-approved* discoveries (Tier-3) back into the library.

### Library entry schema
```yaml
id: range_fade
name: Range mean-reversion
family: mean_reversion          # see catalog families below
horizon: both                   # intraday | swing | both
thesis: "Oversold extensions to a range edge fade; liquidity provision vs transient noise."
watches: [close, range_detect, atr, rsi, avg_volume, realized_vol]
regime: { all_of: [ {gt: ["avg_volume(20)", 1000000]},
                    {between: ["realized_vol(20)", 0.12, 0.45]} ] }
entry:  { when: { all_of: [ {lt: ["rsi(14)", "{entry_rsi}"]},
                             {lt: ["close", "rolling_low({rolling_n})"]} ] },
          action: enter_long, sizing: {vol_scaled: {target_vol: 0.10}} }
exits:  [ {stop_loss: {atr_mult: "{stop_atr}"}},
          {take_profit: {atr_mult: 2.0}},
          {time_stop: {sessions: 7}}, {regime_break_exit: true} ]
param_grid:                     # explicit {param} placeholders filled at sweep time
  rolling_n: {min: 10, max: 40, step: 5, default: 20}
  entry_rsi: {min: 20, max: 40, step: 5, default: 30}
  stop_atr:  {min: 0.6, max: 1.4, step: 0.2, default: 0.9}
scan:
  all_of: [ {gt: ["avg_volume(20)", 1000000]},
            {lt: ["zscore(20)", -1.0]} ]
peers_hint: sector_or_corr
default_universe: {min_price: 5, min_dollar_volume: 5000000}

persistence_thesis:                    # REQUIRED — the structural edge claim (gates_version 4+)
  edge_type: forced_flow               # enum: forced_flow | behavioral | risk_premium | smallness
  structural_reason: |                 # REQUIRED, min ~40 chars.
    Plain-language explanation of who is structurally compelled to trade sub-optimally and why
    arbitrage capital that would correct it is absent, deterred, or capacity-limited.
  forced_counterparty: |               # REQUIRED, min ~40 chars. Who hands you the money.
    e.g. "Index funds mechanically buying reconstitution adds on the effective date."
  death_condition:                     # REQUIRED, list, >=1 non-empty entry.
    - "avg_volume(20) > capacity_ceiling_usd"   # prefer machine-checkable (DSL-referenceable)
  capacity_ceiling_usd: 20000000       # REQUIRED, > 0. Explicit smallness moat.
  monitorable_as_regime: true          # REQUIRED bool. If true, death_conditions must reference
                                       #   DSL primitives or regime fields.
```

**Persistence thesis load-time gate.** Any archetype missing `persistence_thesis` or with an incomplete
one is excluded from exploration (same mechanism as the param-binding exclusion), with a logged
`exclusion_reason` and `status: excluded` surfaced in the Library UI. The gate enforces presence and
well-formedness, not correctness — human review judges whether the thesis is actually true. Rules:
(1) block present, (2) `edge_type` in the enum, (3) `structural_reason` and `forced_counterparty`
meet minimum content length, (4) `death_condition` is a non-empty list with no empty entries,
(5) `capacity_ceiling_usd > 0`, (6) if `monitorable_as_regime: true`, at least one `death_condition`
references a DSL feature primitive or a field from the archetype's regime block.

### Seed catalog (wide — build all on day one)
Each is a DSL template + scan + param grid following the schema above. Families and members:

| Family | Archetypes (id) | Horizon |
|--------|-----------------|---------|
| mean_reversion | `range_fade`, `rsi_reversion`, `bollinger_reversion`, `zscore_reversion`, `gap_fade`, `vwap_reversion` | swing / both / intraday |
| momentum_trend | `donchian_breakout`, `ma_crossover_trend`, `adx_trend_follow`, `pullback_continuation`, `relative_strength_momentum`, `opening_range_breakout` | swing / intraday |
| volatility | `squeeze_breakout`, `atr_channel_breakout`, `keltner_reversion`, `vol_scaled_exposure` | both |
| time_microstructure | `time_of_day_bias`, `end_of_day_drift`, `intraday_momentum_continuation` | intraday |
| cross_sectional | `pairs_statistical`, `sector_relative_strength` | swing |
| forced_flow | `russell_reconstitution_drift` | swing |
| behavioral_drift | `neglected_earnings_drift` | swing |
| structural_filter | `earnings_proximity_filter`, `liquidity_regime_filter` | modifier (composes with any) |

Notes: `structural_filter` archetypes are regime modifiers (e.g. `days_to_event` avoidance), not standalone
trades. Each archetype's full entry/exit/regime/param_grid/scan ships as its YAML file. Intraday archetypes
require a consolidated intraday feed (see doc 12 data sourcing); they degrade to swing if only EOD is wired.

**Forced-flow family** (`forced_flow`): event-driven archetypes that exploit predictable institutional flow
from index reconstitution, ETF rebalancing, or similar mandated trading.  Requires event-calendar data
(reconstitution dates, membership changes) via `MarketDataProvider.reconstitution_events()`, point-in-time.
`SampleDataProvider` includes a deterministic synthetic calendar for testing; Polygon does not provide this
data — a dedicated feed (FTSE Russell, ICE, or vendor) must be wired for production.  Entry is event-relative:
conditioned on `is_index_add` + `days_to_event(russell_effective)` being within a window.

**Behavioral-drift family** (`behavioral_drift`): archetypes that exploit slow information incorporation
in neglected names.  `neglected_earnings_drift` enters after a strong earnings reaction (proxied by
zscore + volume spike) in low-attention names and rides the first leg of post-earnings drift.  Requires
an **earnings calendar** via `MarketDataProvider.earnings_events(symbol, start, end, as_of)`, point-in-time
(announcements only visible once `announce_date <= as_of`).  Each event includes a `session` flag
(`BMO`/`AMC`) that determines the reaction bar.  Entry is event-relative: conditioned on
`days_to_event(earnings)` being in the [-3, -1] window (1-3 sessions post-announcement).  Neglect is
proxied by low `avg_volume(20)`; the `death_condition` fires `regime_break_exit` when attention arrives
(volume crosses the ceiling).  `SampleDataProvider` includes a deterministic synthetic quarterly earnings
calendar; `PolygonDataProvider` requires a financials/reference subscription or dedicated vendor.
V1 uses price-reaction proxy (zscore + volume spike) instead of analyst-estimate SUE data.
**Upgrade path (Phase 2):** real SUE from an estimates vendor; analyst-coverage count + institutional
ownership % from a reference vendor for a sharper neglect filter and death condition.

**Peer-test note for forced_flow:** the standard correlation peer-hit gate assumes a repeatable cross-sectional
pattern. Forced-flow is event-specific; the "peers" are *other reconstitution events across years*, not
correlated tickers. For this family, either adapt the peer test to "hit rate across historical reconstitution
cohorts" or document why the peer gate is replaced by cross-year cohort validation. Do not silently pass
a peer gate that doesn't mean anything.  The `peers_hint: none` flag in the archetype signals this.

### The scan playbook = what it surfaces
This is the answer to "what does it scan for." The `universe_scan` tool runs an archetype's `scan` block
across the universe at `as_of` and returns ranked candidate tickers (rank = fit score: how strongly the
scan conditions hold + liquidity). Candidates feed the agent (author thesis + concrete spec) → backtest →
gauntlet → ledger. No scan = no idea what to look for; the playbook IS the day-one knowledge.

**Scan pipeline** (Polygon path): grouped-daily for the `as_of` date + trailing liquidity window →
filter by `default_universe` (min_price, median dollar-volume over ~20 sessions) → cap at
`scan_universe_cap` (default 500) → fetch bars for survivors → evaluate `scan` DSL conditions
point-in-time (no lookahead — `as_of` clamps bar end dates) → rank by fit score → return.
When no real provider is configured, returns the sample universe with `is_sample_fallback: true`.

**Return shape**: `{candidates: [{ticker, fit_score, archetype, family}], is_sample_fallback: bool}`.
Config params: `scan_universe_cap`, `polygon_calls_per_minute`, `scan_bar_lookback_days`,
`scan_liquidity_window` (all in Settings / env).

### Aggressive exploration workflow (seeded T2; deterministic pipeline, ledger-governed)
```
for archetype in library (filtered by archetype_subset):
    candidates = scan_universe(archetype, as_of)                 # surfaces what to look at
    for ticker in candidates[:candidates_per_archetype]:
        if budget_spent >= budget: break
        bars = provider.bars(ticker, *recent_window(700))
        variants = build_archetype_variants(template, param_grid, max_configs)
        all_returns = [backtest(v, bars) for v in variants]      # sweep all param combos
        winner = argmax(daily_sharpe(all_returns))                # IS-best by equity-curve Sharpe
        competing_returns = dedup(column_stack(all_returns))      # T×N matrix for PBO
        peers = [c.ticker for c in candidates if c != ticker][:5]
        n_eff += 1                                                # one per ticker/archetype family
        ledger.append({spec_hash, ticker, archetype_id, ...})    # every trial counted
        report = validate(winner, bars, n_eff, competing_returns, peers)  # full gauntlet
        if report.passed: register(winner) → survivors           # all 6 gates must pass
```
- N_eff per family rises with the sweep → DSR `expected_max_sharpe` bar rises → harder to pass. By design.
- Survivors go to the Review Queue with their deflated confidence; you approve; paper precedes live.
- Budget cap (config) bounds aggression per cycle; the agent may also *compose across* archetypes (T2) and
  *propose new* archetypes (T3, human-gated) — both ledger-tracked, never relaxing thresholds.

### Param-grid sweep contract (T2 implementation detail)
The T2 loop sweeps the **archetype's declared `param_grid`** — entry lookbacks, thresholds, stop multipliers,
widths — not a hardcoded stop-loss grid. Each YAML archetype declares `{min, max, step, default}` ranges
for its relevant parameters (e.g. `rsi_period`, `rsi_threshold`, `stop_atr` for `rsi_reversion`).

**Explicit placeholder binding.** Templates use `{param_name}` placeholders that the param_grid fills via
exact string substitution — no naming-convention regex inference. A pure-value placeholder (`"{stop_atr}"`)
is replaced with the raw numeric; an embedded placeholder (`"rsi({rsi_period})"`) is string-formatted.
Every param_grid key must have a corresponding `{key}` in the template; every placeholder must have a
param_grid entry with a `default:` value. Violations are caught at archetype load time — any archetype
with an unbound param, unfilled placeholder, or missing default is **excluded from exploration** with a
logged error. Variant distinctness is also spot-checked at load: if sampled combos produce duplicate specs,
the archetype is excluded. This guarantees 0 no-op params feeding PBO.

The sweep:

1. Fills the template with `default` values to produce the **base variant** (variant 0).
2. Computes the full cartesian product of all `param_grid` dimensions.
3. If the product exceeds `pbo.max_configs` (config/validation.yaml, default 20), down-samples via
   deterministic strided selection (seed=42) — evenly spaced across the sorted product, not random truncation.
4. For each selected combination, fills placeholders to produce a variant. **Deduplicates** variants via
   JSON-serialized comparison — identical specs never appear twice in the matrix.
5. Backtests all distinct variants, builds a T×N competing-returns matrix, selects the IS-best config.
6. Passes the full matrix as `competing_returns` to `validate()` → real multi-config PBO (doc 08 §3).
   Reports both `n_configs_swept` and `n_configs_distinct` in survivor dicts.

When no archetype grid is available (non-archetype callers), falls back to stop-loss-only variation.

**n_eff accounting:** `n_eff` increments once per ticker/archetype family (one independent hypothesis),
regardless of how many param configs the grid produces. PBO measures within-family selection-overfitting;
DSR deflates across families. Orthogonal, no double-counting.

## 2. Library / Explore UI (extends the Registry screen)
Registry has two tabs: **Instantiated** (all strategies across the lifecycle) and **Library** (the
archetype catalog), presented in a **master-detail layout**: the left column is the list/cards, the
right column is a docked detail panel (mobile: full-width slide-over). Selection is URL-driven.

- **Library view:** archetype cards grouped by family/theme; filter by family + horizon. Each card shows
  name, thesis (one line), watched features, horizon, and status: `unexplored` / `explored` /
  `has-survivors (n)` / `has-live` / `excluded` (with `exclusion_reason`). An `excluded` archetype
  failed load-time param binding validation — it won't appear in sweeps until the YAML is fixed.
  Surfaces the universe of themes at a glance.
- **Archetype detail (right panel):** full thesis, watched features, the scan logic (human-readable),
  the param grid, and the exploration funnel for it (trials_run → ledger entries → validation outcomes
  → survivors, derived post-hoc from ledger rows). Actions: **Run scan** (surface candidate tickers now), **Explore** (queue the
  aggressive sweep for this archetype, budget-aware), **Author from this** (seed the research agent),
  **Open in Sandbox** (#3).
- **Scan and Explore stream live job activity (AG-UI-style)** into the panel's bottom activity feed.
  Both endpoints return a `job_id`; the client subscribes to `/ws/jobs/{job_id}` via the ws client
  (`web/src/lib/ws.ts`) and normalizes events through `web/src/lib/jobEvents.ts` into lifecycle +
  tool-call semantics (run_started → step_started/finished → run_finished/error). For Explore, the
  exploration funnel counters (trials → backtested → validated → survivors) update in real time; on
  completion, survivors link into the Review Queue. For Scan, candidates render ranked on completion;
  the `is_sample_fallback` banner shows when no real provider is configured. The info section, action
  bar, and activity feed are independent scroll regions — the action bar stays pinned.
- Read/scan/backtest are agent-free reads; nothing here deploys.

## 3. Backtest Sandbox (new screen) + ad-hoc backtest endpoint
A hands-on screen to test without going through the agent flow.
- **Source:** a registry strategy version, OR a library archetype + chosen params, OR a pasted/edited DSL spec.
- **Inputs:** ticker(s), date range, bar timeframe, mode = `backtest_only` | `full_gauntlet`.
- **Run → results:** equity curve, trade list, core metrics; in `full_gauntlet` mode also DSR, PBO, robustness,
  and the deflated confidence (doc 08). Deterministic; runs on whichever `Backtester` impl is active behind
  the interface (custom Python today; nautilus_trader when wired in M9) + the real harness, so sandbox
  results are trustworthy, not a toy.
- **Guardrail:** the sandbox can promote a result into Research/Registry, but NEVER to live — live still
  requires the full validation + human Approval gates. Every run logs to the ledger (it's still search).

## API additions (doc 09 surface)
```
GET    /library                      # archetypes + status
GET    /library/{id}                 # detail + exploration funnel
POST   /library/{id}/scan            # body {universe?, as_of?} -> ranked candidates
POST   /library/{id}/explore         # body {budget, param_grid?} -> job_id (ledger-tracked sweep)
POST   /backtest                     # body {source: spec|{archetype_id,params}|strategy_version_id,
                                      #       tickers[], start, end, timeframe, mode} -> job_id -> results
```

## Data model additions (doc 09)
**Planned — not yet implemented.** Currently archetypes are loaded in-memory from
`config/library/*.yaml` on every startup (templates now use `{param}` placeholders + `default:`
values). When the DB-backed tables below land, add a re-seed migration to populate them from the
current YAML format.
```
library_archetypes(id pk, name, family, horizon, thesis, template jsonb, scan jsonb,
                   param_grid jsonb, source enum(seed,evolved), status, created_at)
exploration_runs(id pk, archetype_id fk, budget_spent, trials int, survivors int, ts)
```
(Trials themselves live in the existing `search_ledger`; archetype family = `hypothesis_family`.)

## Build sequence placement (doc 06)
- After **M4 (DSL)**: load the seed library (archetypes are DSL templates) + `universe_scan` over scans.
- After **M3 + M4**: Backtest Sandbox endpoint + the manual run path (engine + harness already exist).
- In **M7 (UI)**: Library/Explore tabs on Registry + the Backtest Sandbox screen.
- In **M8 (Evolution)**: the aggressive exploration workflow (seeded wide), governed by the ledger + budget;
  Tier-3 promotes proven discoveries into the library.

## Safety invariants (unchanged)
Archetypes are DSL templates (type-checked, no executable code) and scans are DSL conditions (deterministic).
Exploration is a deterministic pipeline; the LLM authors theses/specs but never sizes/places orders. Every
trial counts toward N_eff; thresholds never relax. Nothing auto-deploys; live needs the gauntlet + Approval.
