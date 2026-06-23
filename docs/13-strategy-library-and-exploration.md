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
Seeds live as YAML in `config/library/*.yaml`, loaded into a `library_archetypes` table on init; editable;
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
```

### Seed catalog (wide — build all on day one)
Each is a DSL template + scan + param grid following the schema above. Families and members:

| Family | Archetypes (id) | Horizon |
|--------|-----------------|---------|
| mean_reversion | `range_fade`, `rsi_reversion`, `bollinger_reversion`, `zscore_reversion`, `gap_fade`, `vwap_reversion` | swing / both / intraday |
| momentum_trend | `donchian_breakout`, `ma_crossover_trend`, `adx_trend_follow`, `pullback_continuation`, `relative_strength_momentum`, `opening_range_breakout` | swing / intraday |
| volatility | `squeeze_breakout`, `atr_channel_breakout`, `keltner_reversion`, `vol_scaled_exposure` | both |
| time_microstructure | `time_of_day_bias`, `end_of_day_drift`, `intraday_momentum_continuation` | intraday |
| cross_sectional | `pairs_statistical`, `sector_relative_strength` | swing |
| structural_filter | `earnings_proximity_filter`, `liquidity_regime_filter` | modifier (composes with any) |

Notes: `structural_filter` archetypes are regime modifiers (e.g. `days_to_event` avoidance), not standalone
trades. Each archetype's full entry/exit/regime/param_grid/scan ships as its YAML file. Intraday archetypes
require a consolidated intraday feed (see doc 12 data sourcing); they degrade to swing if only EOD is wired.

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
for archetype in library (budget-ordered):
    candidates = universe_scan(archetype.scan, as_of=now)        # surfaces what to look at
    for ticker in candidates[:k]:
        for params in grid(archetype.param_grid):                # the aggressive sweep
            spec = instantiate(archetype, ticker, params)
            bt   = backtest(spec); ledger.log(spec, family=archetype.family)   # every trial counted
            if bt.passes_cheap_screen: report = validate(spec)   # full gauntlet (doc 08)
    surface survivors where survivor_count > expected_false_discoveries(α, n_eff(family))
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
Registry gains two tabs: **Instantiated** (today's registry: all strategies across the lifecycle) and
**Library** (the archetype catalog).
- **Library view:** archetype cards grouped by family/theme; filter by family + horizon. Each card shows
  name, thesis (one line), watched features, horizon, and status: `unexplored` / `explored` /
  `has-survivors (n)` / `has-live`. Surfaces the universe of themes at a glance.
- **Archetype detail:** full thesis, watched features, the scan logic (human-readable), the param grid, and
  the exploration funnel for it (trials → backtested → validated → survivors, pulled from the ledger).
  Actions: **Run scan** (surface candidate tickers now), **Explore** (queue the aggressive sweep for this
  archetype, budget-aware), **Author from this** (seed the research agent), **Open in Sandbox** (#3).
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
